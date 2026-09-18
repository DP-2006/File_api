import os
import time
from django.conf import settings

try:
    import yara
    YARA_AVAILABLE = True
except ImportError:
    YARA_AVAILABLE = False


class YaraEngine:
    name = 'yara'

    def __init__(self):
        self.rules_dir = os.path.join(settings.BASE_DIR, 'multi_av', 'yara_rules')

    def scan(self, file_path):
        start = time.time()
        if not YARA_AVAILABLE:
            return {'score': 0, 'threat': False, 'error': 'yara not installed',
                    'duration_ms': 0}

        try:
            matches = []
            if os.path.exists(self.rules_dir):
                for root, _, files in os.walk(self.rules_dir):
                    for f in files:
                        if f.endswith(('.yar', '.yara')):
                            try:
                                rules = yara.compile(filepath=os.path.join(root, f))
                                m = rules.match(file_path)
                                for match in m:
                                    matches.append({
                                        'rule': match.rule,
                                        'tags': list(match.tags),
                                        'meta': dict(match.meta) if match.meta else {}
                                    })
                            except Exception:
                                continue

            duration = int((time.time() - start) * 1000)
            if matches:
                score = min(100, len(matches) * 40)
                for m in matches:
                    if m.get('meta', {}).get('severity') == 'critical':
                        score = 100
                        break
                return {'score': score, 'threat': True,
                        'details': f'YARA: {", ".join(m["rule"] for m in matches)}',
                        'duration_ms': duration, 'raw': {'matches': matches}}

            return {'score': 0, 'threat': False, 'details': 'no yara match',
                    'duration_ms': duration, 'raw': {}}

        except Exception as e:
            return {'score': 0, 'threat': False, 'error': str(e),
                    'duration_ms': int((time.time() - start) * 1000)}

    def status(self):
        return {
            'active': YARA_AVAILABLE,
            'rules_dir': self.rules_dir,
            'rules_count': self._count_rules(),
        }

    def _count_rules(self):
        count = 0
        if os.path.exists(self.rules_dir):
            for root, _, files in os.walk(self.rules_dir):
                count += sum(1 for f in files if f.endswith(('.yar', '.yara')))
        return count


yara_engine = YaraEngine()