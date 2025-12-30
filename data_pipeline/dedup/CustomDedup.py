import contextlib
import hashlib
import struct
import numpy as np

from datatrove.data import DocumentsPipeline
from datatrove.io import DataFolderLike, get_datafolder
from datatrove.pipeline.base import PipelineStep
from datatrove.pipeline.writers.disk_base import DiskWriter
from datatrove.utils.binaryio import read_tuples_from_file
from datatrove.utils.logging import logger
from datatrove.utils.typeshelper import StatHints

class ExactDeduplication(PipelineStep):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.seen_hashes = set()

    def run(self, data, rank=0, world_size=1):
        for doc in data:
            # SHA-256 hash
            doc_hash = hashlib.sha256(doc.text.encode('utf-8')).hexdigest()
            
            # drop if seen
            if doc_hash in self.seen_hashes:
                continue
            
            # first to keep
            self.seen_hashes.add(doc_hash)
            yield doc

class MinhashDedupFilter(PipelineStep):
    """Minhash Deduplication: Fourth (and final) Pipeline Step

    Return the documents with the minhash clusters
    """

    type = "🫂 - DEDUP"
    name = "🎯 MinHash stage 4"

    def __init__(
        self,
        input_folder: DataFolderLike,
        date_key: str,
        exclusion_writer: DiskWriter = None,
        lines_to_buffer: int = 5
    ):
        super().__init__()
        self.data_folder = get_datafolder(input_folder)
        self.date_key = date_key
        self.exclusion_writer = exclusion_writer
        self.lines_to_buffer = lines_to_buffer

    def _drop_doc(self, doc, rank: int, *, reason: str, is_duplicate: bool) -> None:
        """Mark a doc as dropped and optionally write it to the exclusion writer."""
        self.stat_update(StatHints.dropped)
        doc.metadata["is_duplicate"] = is_duplicate
        doc.metadata["drop_reason"] = reason
        if self.exclusion_writer:
            self.exclusion_writer.write(doc, rank)

    def _extract_yyyy_mm_dd(self, raw_value) -> str | None:
        """Return YYYY-MM-DD if available; otherwise None."""
        if not raw_value:
            return None
        # Many inputs are ISO strings; we only keep the date portion.
        s = str(raw_value)
        if len(s) < 10:
            return None
        date_part = s[:10]
        # Basic sanity check; avoids passing obviously broken dates.
        if date_part[4:5] != "-" or date_part[7:8] != "-":
            return None
        return date_part


    def run(self, data: DocumentsPipeline, rank: int = 0, world_size: int = 1):
        cluster_file = f"{rank:06d}.clusters"
        logger.info(f"📥 Loading cluster info from {cluster_file}...")

        if not self.data_folder.isfile(cluster_file):
            logger.warning(f"No .remove file for {rank=}.")
            for doc in data:
                self.stat_update(StatHints.total, StatHints.forwarded)
                yield doc
            return

        def metadata_loader(file):
            with self.data_folder.open(file, "rb") as metadata_f:
                yield from read_tuples_from_file(metadata_f, "2I", lines_to_buffer=self.lines_to_buffer)

        cluster_loader = metadata_loader(f"{rank:06d}.clusters")
        doc_to_cluster = {next_cluster[0] : next_cluster[1]  for next_cluster in cluster_loader}

        cluster_seen_records = {}

        logger.info("🚀 Starting Medical Deduplication (Same Patient & Same Day Check)...")
        
        for idx, doc in enumerate(data):
            # A. check cluster id
            cid = doc_to_cluster.get(idx, -1)
            doc.metadata["minhash_cluster_id"] = int(cid)

            # B. singleton cluster always survive
            if cid == -1:
                self.stat_update(StatHints.forwarded)
                yield doc
                continue

            # C. extract patient_id + chunk_id and event_date. event_date has "YYYY-MM-DD: ...." format
            pid = doc.id
            raw_evt_date = doc.metadata.get(self.date_key)

            # If no/invalid event_date -> faulty session, drop it.
            evt_date = self._extract_yyyy_mm_dd(raw_evt_date)
            if evt_date is None:
                self._drop_doc(doc, rank, reason="invalid metadata date", is_duplicate=False)
                continue

            # D. get record key
            record_key = (pid, evt_date)

            # E. identify duplicates
            if cid not in cluster_seen_records:
                cluster_seen_records[cid] = set()
            
            if record_key in cluster_seen_records[cid]:
                # 💥 Caught! Same cluster (similar content) + same patient + same date
                # This is a true duplicate or system error -> drop
                self._drop_doc(doc, rank, reason="same_patient_same_day_in_cluster", is_duplicate=True)
                continue
            
            else:
                # ✅ Survived!
                # Similar content (same cluster) but different date -> valuable as follow-up data
                cluster_seen_records[cid].add(record_key)
                
                self.stat_update(StatHints.forwarded)
                doc.metadata["is_duplicate"] = False
                yield doc
