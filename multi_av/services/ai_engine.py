import re
import time


class AIEngine:
    name = 'ai'

    def scan(self, file_path, file_obj=None):
        start = time.time()
        try:
            from core.services.llm_service import llm_service
            if not llm_service or not llm_service.is_available:
                return {'score': 0, 'threat': False, 'error': 'AI unavailable',
                        'duration_ms': 0}

            content = ''
            try:
                from core.services.file_reader import FileReader
                if file_obj:
                    info = FileReader.read_file(file_obj.file)
                    content = (info.get('content') or '')[:2000]
            except Exception:
                pass

            prompt = (
                f'فایل "{file_path}" را از نظر امنیتی تحلیل کن.\n'
                f'محتوای خلاصه: {content}\n'
                'فقط یک عدد بین 0 تا 100 بده که میزان خطرناک بودن را نشان دهد. فقط عدد.'
            )
            resp = llm_service._call_llm_stream(prompt)
            m = re.search(r'\d+', resp or '')
            score = min(100, int(m.group())) if m else 0

            return {
                'score': score,
                'threat': score >= 60,
                'details': f'AI score: {score}',
                'duration_ms': int((time.time() - start) * 1000),
                'raw': {'response': resp[:500]}
            }
        except Exception as e:
            return {'score': 0, 'threat': False, 'error': str(e),
                    'duration_ms': int((time.time() - start) * 1000)}

    def status(self):
        try:
            from core.services.llm_service import llm_service
            return {'active': bool(llm_service and llm_service.is_available)}
        except Exception:
            return {'active': False}


ai_engine = AIEngine()