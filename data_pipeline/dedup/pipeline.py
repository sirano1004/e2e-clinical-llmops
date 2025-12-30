# data_pipeline/dedup/pipeline.py
import os
import traceback

from .CustomDedup import ExactDeduplication, MinhashDedupFilter
from .path import DedupPaths
from ..config import settings

from datatrove.executor import LocalPipelineExecutor

from datatrove.pipeline.dedup import (
    MinhashDedupBuckets, 
    MinhashDedupSignature, 
    MinhashDedupCluster,
    MinhashConfig
)
from datatrove.pipeline.readers import JsonlReader
from datatrove.pipeline.writers import JsonlWriter
from datatrove.utils.typeshelper import Languages

CPU = os.cpu_count()
workers = max(1, CPU - 1)
tasks = workers * 2

config = MinhashConfig(
    n_grams=settings.n_gram, 
    num_buckets=settings.num_buckets, 
    hashes_per_bucket=settings.hashes_per_bucket
)

def run_pipeline(input_dir, inter_dir, output_dir, target) -> None:
    paths = DedupPaths(input_dir, inter_dir, output_dir, target)

    dirs = [
        paths.hard_output(),
        paths.signatures(),
        paths.buckets(),
        paths.clusters(),
        paths.removed(),
        paths.final_output()
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

    # ---------------------------------------------------------
    # [Step 1] Hard Dedup
    # ---------------------------------------------------------
    print("🚀 [Step 1] Running Hard Deduplication (Exact)...")
    step1 = LocalPipelineExecutor(
        pipeline=[
            JsonlReader(input_dir, text_key=settings.dedup_text_key, id_key=settings.dedup_id_key, glob_pattern = paths.input_pattern()),
            ExactDeduplication(),
            JsonlWriter(paths.hard_output(), expand_metadata = True),
        ],
        tasks=1, workers=1,
    )
    step1.run()

    # ---------------------------------------------------------
    # [Step 2] Soft Dedup
    # ---------------------------------------------------------
    print("🚀 [Step 2] Processing Soft Deduplication ...")

    # 3-B-1: Generate Signatures
    step2_sig = LocalPipelineExecutor(
        pipeline=[
            JsonlReader(paths.hard_output(), text_key=settings.dedup_text_key, id_key=settings.dedup_id_key),
            MinhashDedupSignature(
                output_folder=paths.signatures(),
                config=config,
                language=Languages.english
            )
        ],
        tasks=tasks, workers=workers
    )
    step2_sig.run()

    # 3-B-2: Generate Buckets
    step2_bucket = LocalPipelineExecutor(
        pipeline=[
            MinhashDedupBuckets(
                input_folder=paths.signatures(),
                output_folder=paths.buckets(),
                config=config,
            )
        ],
        tasks=settings.num_buckets, workers=workers
    )
    step2_bucket.run()
    
    step3_cluster = LocalPipelineExecutor(
        pipeline=[
            MinhashDedupCluster(
                input_folder=paths.buckets(),
                output_folder=paths.clusters(),
                config=config,
                save_cluster_id=True
            )
        ],
        tasks=1, workers=workers
    )
    step3_cluster.run()

    step4_filter = LocalPipelineExecutor(
        pipeline=[
            JsonlReader(paths.hard_output(), text_key=settings.dedup_text_key, id_key=settings.dedup_id_key),
            MinhashDedupFilter(
                input_folder=paths.clusters(),
                date_key=settings.dedup_date_key,
                exclusion_writer=JsonlWriter(paths.removed(), compression = None, expand_metadata = True)
            ),
            JsonlWriter(paths.final_output(), paths.output_pattern(), compression = None, expand_metadata = True)
        ],
        tasks=tasks, workers=workers
    )

    step4_filter.run()

    print("✅ All Dedup Preparation Finished!")

def main():
    input_dir = os.path.join(settings.data_dir, settings.parsed_data_dir)
    inter_dir = os.path.join(settings.data_dir, settings.dedup_data_dir, settings.hard_dedup_dir)
    output_dir = os.path.join(settings.data_dir, settings.dedup_data_dir, settings.soft_dedup_dir)

    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Parsed data not found at: {input_dir}")

    targets = ['dpo', 'sft']
    for target in targets:
        try:
           run_pipeline(input_dir, inter_dir, output_dir, target)
        except Exception as e:
            print(f"❌ Error processing {target}: {e}")
            traceback.print_exc()
            continue

if __name__ == "__main__":
    main()