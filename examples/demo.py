"""Run from the repository root: python -m examples.demo"""
import json
from preference import PreferenceService, SQLiteStorage


def main():
    with SQLiteStorage(":memory:") as storage:
        service = PreferenceService(storage)
        service.add_rating("demo", "blush", [0.7, 0.12, 0.04], 1)
        products = [
            {"name": "Near reference", "color": [0.71, 0.12, 0.05]},
            {"name": "Distant shade", "color": [0.2, 0, 0]},
        ]
        print(json.dumps(service.recommend("demo", "blush", products), indent=2))


if __name__ == "__main__":
    main()
