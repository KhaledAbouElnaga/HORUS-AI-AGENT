import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from horus_local_voice import Event, VoiceHarness


def main():
    fixture = json.loads((Path(__file__).parents[1] / 'tests/fixtures/turns.json').read_text(encoding='utf-8'))
    events = [Event('speech_final', row['text'], event_id=str(i)) for i, row in enumerate(fixture)]
    result = VoiceHarness().run(events)
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
