from dataclasses import dataclass
import os

@dataclass(frozen=True)
class DedupPaths:
    base_input: str
    base_intermediate: str
    base_output: str
    target: str

    def hard_input(self):
        return self.base_input

    def hard_output(self):
        return os.path.join(self.base_intermediate, self.target)

    def signatures(self):
        return os.path.join(self.base_output, "signatures", self.target)

    def buckets(self):
        return os.path.join(self.base_output, "buckets", self.target)

    def clusters(self):
        return os.path.join(self.base_output, "clusters", self.target)

    def removed(self):
        return os.path.join(self.base_output, "removed", self.target)

    def final_output(self):
        return os.path.join(self.base_output, "outputs")

    def output_pattern(self):
        return f"{self.target}_${{rank}}.jsonl"
    
    def input_pattern(self):
        return f"{self.target}*.jsonl"