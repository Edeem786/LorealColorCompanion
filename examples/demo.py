"""Run from the repository root: python -m examples.demo"""
import json
from preference import PreferenceService, SQLiteStorage


def main():
    # In-memory demo avoids adding duplicate events each time it runs.
    with SQLiteStorage(":memory:") as storage:
        model = PreferenceService(storage)
        model.add_rating("demo", "blush", [0.7, 0.12, 0.04], 1)
        model.add_rating("demo", "blush", [0.5, 0.25, 0.15], -1)
        model.add_comparison("demo", "lip", [0.6, 0.1, 0.04], [0.4, 0.2, 0.1], "a")
        print(json.dumps(model.rank_colors("demo", "blush", [
            {"name": "Sample 01", "color": [0.71, 0.12, 0.05], "finish": "matte"},
            {"name": "Sample 02", "color": [0.51, 0.24, 0.15]},
        ]), indent=2))


if __name__ == "__main__":
    main()
