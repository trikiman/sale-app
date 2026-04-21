import json

from database.sale_history import SESSION_GAP_MINUTES, repair_false_reentries


def main():
    result = repair_false_reentries(max_gap_minutes=SESSION_GAP_MINUTES)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
