from __future__ import annotations

import json

from sentineldrive_worker.pipeline import run_processing_pipeline


def main() -> None:
    print(json.dumps(run_processing_pipeline(), default=str, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
