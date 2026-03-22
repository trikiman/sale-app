import nodriver as uc

print("uc.cdp dir:", dir(uc.cdp))
if hasattr(uc.cdp, 'input_'):
    print("Has input_:", dir(uc.cdp.input_))
elif hasattr(uc.cdp, 'input'):
    print("Has input:", dir(uc.cdp.input))
else:
    print("No input domain found!")
