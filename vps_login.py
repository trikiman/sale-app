"""
VkusVill Login Helper - Opens Chrome with VNC for one-time login
Uses SeleniumBase UC mode with persistent profile
"""
from seleniumbase import SB
import subprocess
import time
import os
import signal

PROFILE_DIR = os.path.expanduser("~/.vkusvill_profile")

def login_interactive():
    print("=" * 60)
    print("VkusVill Interactive Login (SeleniumBase UC)")
    print("=" * 60)
    
    os.makedirs(PROFILE_DIR, exist_ok=True)
    
    # Start x11vnc on the virtual display
    print("\nStarting VNC server...")
    
    # Use SB with visible display for VNC
    with SB(uc=True, headless=False, xvfb=True, user_data_dir=PROFILE_DIR) as sb:
        # Get the display number and start VNC
        display = os.environ.get('DISPLAY', ':99')
        print(f"Display: {display}")
        
        # Start x11vnc pointing to this display
        vnc_process = subprocess.Popen(
            ['x11vnc', '-display', display, '-forever', '-shared', '-rfbport', '5900', '-nopw', '-xkb'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        print("\n" + "=" * 60)
        print("✅ VNC SERVER STARTED!")
        print("=" * 60)
        print("Connect with a VNC client to:")
        print("   13.61.32.243:5900")
        print("=" * 60)
        print("(No password needed)")
        print("\nOpening VkusVill...")
        
        sb.open("https://vkusvill.ru/cart/")
        time.sleep(5)
        
        print("\n" + "=" * 60)
        print("INSTRUCTIONS:")
        print("1. Connect to VNC at 13.61.32.243:5900")
        print("2. Log in to your VkusVill account in the browser")
        print("3. Make sure you see 'Зелёные ценники' (Green prices)")
        print("4. After login, press Ctrl+C here to save & exit")
        print("=" * 60)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n✅ Login complete! Session saved.")
        finally:
            vnc_process.terminate()
    
    print(f"\nProfile saved to: {PROFILE_DIR}")
    print("Now run: python3 ~/scraper.py")


if __name__ == "__main__":
    login_interactive()
