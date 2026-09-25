import os
import time
import tempfile
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import yara

RULES_DIR = "/app/rules"
_rules = None


def _load_rules():
    global _rules
    filepaths = {}
    for root, _, files in os.walk(RULES_DIR):
        for f in files:
            if f.endswith(('.yar', '.yara')):
                filepaths[os.path.splitext(f)[0]] = os.path.join(root, f)
    try:
        _rules = yara.compile(filepaths=filepaths)
        print(f"Loaded {len(filepaths)} rule files")
    except Exception as e:
        print(f"Error: {e}")
        _rules = None


# Load on import (worker startup)
_load_rules()


@require_http_methods(["GET"])
def health(request):
    return JsonResponse({"status": "ok", "rules_loaded": _rules is not None})


@require_http_methods(["POST"])
def reload_rules(request):
    _load_rules()
    return JsonResponse({"status": "reloaded"})


@csrf_exempt
@require_http_methods(["POST"])
def scan(request):
    if _rules is None:
        return JsonResponse({"error": "rules not loaded", "score": 0, "threat": False}, status=500)

    if 'file' not in request.FILES:
        return JsonResponse({"error": "no file", "score": 0, "threat": False}, status=400)

    start = time.time()
    uploaded = request.FILES['file']

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        for chunk in uploaded.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        matches = _rules.match(tmp_path)
        results = [{"rule": m.rule, "tags": list(m.tags),
                    "meta": dict(m.meta) if m.meta else {}} for m in matches]

        if results:
            score = min(100, len(results) * 40)
            for r in results:
                if r.get("meta", {}).get("severity") == "critical":
                    score = 100
                    break
            threat = True
        else:
            score, threat = 0, False

        return JsonResponse({
            "score": score, "threat": threat,
            "details": f"YARA: {', '.join(r['rule'] for r in results)}" if results else "no match",
            "matches": results,
            "duration_ms": int((time.time() - start) * 1000),
        })
    finally:
        os.unlink(tmp_path)
