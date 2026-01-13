#!/usr/bin/env python3
"""
Interactive Modal.com Setup Wizard
Makes deployment easy with step-by-step guidance
"""

import subprocess
import sys
import os


def print_header(text):
    """Print a nice header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_step(number, text):
    """Print a step"""
    print(f"\n{'─' * 70}")
    print(f"STEP {number}: {text}")
    print('─' * 70)


def run_command(cmd):
    """Run a command and return success status"""
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0


def check_modal_installed():
    """Check if Modal is installed"""
    result = subprocess.run(
        ["python", "-m", "modal", "--version"],
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def check_authenticated():
    """Check if user is authenticated with Modal"""
    result = subprocess.run(
        ["python", "-m", "modal", "token", "list"],
        capture_output=True,
        text=True
    )
    return result.returncode == 0 and "No token" not in result.stdout


def main():
    print_header("🚀 Modal.com Setup Wizard - AI Image Checker")
    
    print("This wizard will guide you through deploying your AI Image Checker")
    print("to Modal.com. It will:")
    print()
    print("  1. ✓ Check if Modal is installed")
    print("  2. ✓ Authenticate with Modal")
    print("  3. ✓ Deploy your application")
    print("  4. ✓ Show you how to test it")
    print()
    
    response = input("Ready to start? (y/n): ")
    if response.lower() != 'y':
        print("\nSetup cancelled. Run this script again when ready!")
        return
    
    # =========================================================================
    # STEP 1: Check Modal Installation
    # =========================================================================
    print_step(1, "Checking Modal Installation")
    
    if check_modal_installed():
        print("✓ Modal is already installed!")
    else:
        print("⚠ Modal is not installed")
        print("\nInstalling Modal...")
        
        if run_command("pip install modal"):
            print("✓ Modal installed successfully!")
        else:
            print("\n❌ Failed to install Modal")
            print("Try manually: pip install modal")
            return
    
    # =========================================================================
    # STEP 2: Authentication
    # =========================================================================
    print_step(2, "Modal Authentication")
    
    if check_authenticated():
        print("✓ You're already authenticated with Modal!")
        
        response = input("\nDo you want to re-authenticate? (y/n): ")
        if response.lower() == 'y':
            print("\nOpening browser for authentication...")
            print("Please complete the authentication and close the browser tab.")
            input("\nPress Enter when ready to continue...")
            
            if run_command("python -m modal setup"):
                print("✓ Re-authenticated successfully!")
            else:
                print("\n❌ Authentication failed")
                return
    else:
        print("⚠ You need to authenticate with Modal")
        print("\nThis will open your browser for authentication.")
        print("Please:")
        print("  1. Complete the authentication in the browser")
        print("  2. Close the browser tab")
        print("  3. Come back here")
        
        input("\nPress Enter to open browser...")
        
        if run_command("python -m modal setup"):
            print("\n✓ Authentication successful!")
        else:
            print("\n❌ Authentication failed")
            print("Try manually: python -m modal setup")
            return
    
    # =========================================================================
    # STEP 3: Check Files
    # =========================================================================
    print_step(3, "Checking Required Files")
    
    required_files = [
        "modal_handler.py",
        "quality_service.py",
        "ocr_service.py",
        "clip_service.py",
        "qwen_service.py"
    ]
    
    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} - MISSING!")
            missing_files.append(file)
    
    if missing_files:
        print(f"\n❌ Missing required files: {', '.join(missing_files)}")
        print("Make sure all files are in the current directory.")
        return
    
    print("\n✓ All required files present!")
    
    # =========================================================================
    # STEP 4: Deploy
    # =========================================================================
    print_step(4, "Deploying to Modal")
    
    print("This will:")
    print("  • Build a container image with your code")
    print("  • Download AI models (~3-5GB)")
    print("  • Deploy to Modal's cloud")
    print()
    print("⏱ First deployment may take 5-10 minutes")
    print()
    
    response = input("Start deployment? (y/n): ")
    if response.lower() != 'y':
        print("\nDeployment cancelled.")
        return
    
    print("\n🚀 Deploying... (this may take a while)")
    print()
    
    # Run deployment and show output
    result = subprocess.run(
        ["python", "-m", "modal", "deploy", "modal_handler.py"],
        text=True
    )
    
    if result.returncode != 0:
        print("\n❌ Deployment failed")
        print("\nTroubleshooting:")
        print("  • Check your internet connection")
        print("  • Make sure all service files are present")
        print("  • Try: modal deploy modal_handler.py")
        return
    
    # =========================================================================
    # SUCCESS!
    # =========================================================================
    print_header("🎉 DEPLOYMENT SUCCESSFUL!")
    
    print("Your AI Image Checker is now live on Modal!")
    print()
    print("📋 NEXT STEPS:")
    print()
    print("1. Find your endpoint URL in the output above")
    print("   Look for: https://[your-username]--ai-image-checker-check-image-endpoint.modal.run")
    print()
    print("2. Test your deployment:")
    print("   • Update test_modal.py with your endpoint URL")
    print("   • Run: python test_modal.py")
    print()
    print("3. View logs:")
    print("   • Run: modal logs ai-image-checker")
    print()
    print("4. Visit dashboard:")
    print("   • https://modal.com/apps")
    print()
    print("📚 DOCUMENTATION:")
    print("   • Quick Start: QUICKSTART_MODAL.md")
    print("   • Full Guide: MODAL.md")
    print("   • Comparison: RUNPOD_VS_MODAL.md")
    print()
    
    response = input("Would you like to see the logs now? (y/n): ")
    if response.lower() == 'y':
        print("\nShowing logs (Ctrl+C to exit)...")
        subprocess.run(["python", "-m", "modal", "logs", "ai-image-checker"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup interrupted. Run again when ready!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("Please try manual setup:")
        print("  1. pip install modal")
        print("  2. python -m modal setup")
        print("  3. modal deploy modal_handler.py")
        sys.exit(1)
