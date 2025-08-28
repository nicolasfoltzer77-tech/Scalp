import os
if os.getenv("SCALP_SKIP_BOOT","1") == "1":
    # default = skip; scripts will manage deps explicitly
    raise SystemExit
# sinon: si tu tiens à un mini bootstrap, fais-le ici mais léger