import os
import math
import time


class HeuristicEngine:
    name = 'heuristic'

    SUSPICIOUS_EXT = ['.exe', '.dll', '.bat', '.cmd', '.ps1', '.sh',
                      '.vbs', '.js', '.jar', '.scr', '.msi', '.hta']
    SUSPICIOUS_KEYWORDS = [
        b'powershell', b'cmd.exe', b'wget ', b'curl ',
        b'base64', b'eval(', b'exec(', b'/etc/passwd',
        b'mimikatz', b'keylogger', b'ransomware',
    ]

    def scan(self, file_path):
        start = time.time()
        score = 0
        reasons = []

        file_name = os.path.basename(file_path)

        ext = os.path.splitext(file_name)[1].lower()
        if ext in self.SUSPICIOUS_EXT:
            score += 20
            reasons.append(f'suspicious ext: {ext}')

        try:
            with open(file_path, 'rb') as f:
                data = f.read(1024 * 1024)
            if data:
                entropy = self._entropy(data)
                if entropy > 7.5:
                    score += 40
                    reasons.append(f'entropy={entropy:.2f}')
                elif entropy > 7.0:
                    score += 20
                    reasons.append(f'entropy={entropy:.2f}')
        except Exception:
            pass

        try:
            with open(file_path, 'rb') as f:
                content = f.read(2 * 1024 * 1024).lower()
            for kw in self.SUSPICIOUS_KEYWORDS:
                if kw in content:
                    score += 10
                    reasons.append(f'kw={kw.decode(errors="ignore")}')
        except Exception:
            pass

        score = min(100, score)
        return {
            'score': score,
            'threat': score >= 50,
            'details': '; '.join(reasons) or 'no flags',
            'duration_ms': int((time.time() - start) * 1000),
            'raw': {'reasons': reasons}
        }

    def _entropy(self, data):
        if not data:
            return 0
        counts = [0] * 256
        for b in data:
            counts[b] += 1
        ent, length = 0, len(data)
        for c in counts:
            if c:
                p = c / length
                ent -= p * math.log2(p)
        return ent

    def status(self):
        return {'active': True}


heuristic_engine = HeuristicEngine()