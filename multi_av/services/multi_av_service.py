import hashlib
import os
from django.conf import settings
from django.utils import timezone

from .clamav_engine import clamav_engine
from .yara_engine import yara_engine
from .virustotal_engine import virustotal_engine
from .heuristic_engine import heuristic_engine
from .ai_engine import ai_engine


class MultiAVService:
    """Orchestrator — موتورها رو اجرا می‌کنه، ولی خودشون در Celery task اجرا میشن"""

    def __init__(self):
        self.config = settings.MULTI_AV
        self.enabled = self.config.get('ENABLED_ENGINES', [])
        self.weights = self.config.get('WEIGHTS', {})

        self.engines = {
            'clamav': clamav_engine,
            'yara': yara_engine,
            'virustotal': virustotal_engine,
            'heuristic': heuristic_engine,
            'ai': ai_engine,
        }

    def get_engine(self, name):
        return self.engines.get(name)

    def calculate_final_score(self, results):
        """Voting Engine"""
        total_w = 0
        weighted = 0
        threat_votes = 0
        total_engines = 0

        for name, res in results.items():
            if res.get('error') and res.get('score', 0) == 0:
                continue
            w = self.weights.get(name, 1.0)
            weighted += res.get('score', 0) * w
            total_w += w
            total_engines += 1
            if res.get('threat'):
                threat_votes += 1

        score = int(weighted / total_w) if total_w else 0

        if total_engines and threat_votes / total_engines >= 0.5:
            score = max(score, 70)

        is_threat = score >= self.config.get('THREAT_THRESHOLD', 50)
        if score >= self.config.get('CRITICAL_THRESHOLD', 80):
            severity = 'critical'
        elif score >= 60:
            severity = 'high'
        elif score >= 40:
            severity = 'medium'
        elif score >= 20:
            severity = 'low'
        else:
            severity = 'clean'

        verdict = 'clean' if not is_threat else f'threat ({severity})'
        return {'score': score, 'is_threat': is_threat,
                'severity': severity, 'verdict': verdict}

    def get_all_engines_status(self):
        statuses = {}
        for name, eng in self.engines.items():
            try:
                statuses[name] = eng.status()
            except Exception as e:
                statuses[name] = {'active': False, 'error': str(e)}
        return statuses


multi_av = MultiAVService()