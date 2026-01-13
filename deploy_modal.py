"""
Quick deployment script for Modal.com
"""

import subprocess
import sys


def run_command(cmd, description):
    """Run a command and print status"""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}\n")
    
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode != 0:
        print(f"\n❌ Failed: {description}")
        return False
    
    print(f"\n✅ Success: {description}")
    return True


def main():
    print("=" * 60)
    print("Modal.com Deployment Script")
    print("=" * 60)
    
    print("\nThis script will:")
    print("1. Install Modal CLI")
    print("2. Authenticate with Modal")
    print("3. Deploy your application")
    
    response = input("\nContinue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    # Step 1: Install Modal
    if not run_command(
        "pip install modal",
        "Installing Modal CLI"
    ):
        print("\n⚠️ Installation failed. Try manually: pip install modal")
        return
    
    # Step 2: Setup Modal
    print("\n" + "=" * 60)
    print("🔐 Setting up Modal Authentication")
    print("=" * 60)
    print("Your browser will open. Please authenticate and close the tab.")
    input("\nPress Enter to continue...")
    
    if not run_command(
        "python -m modal setup",
        "Authenticating with Modal"
    ):
        print("\n⚠️ Authentication failed. Try manually: python -m modal setup")
        return
    
    # Step 3: Deploy
    print("\n" + "=" * 60)
    print("📦 Deploying to Modal")
    print("=" * 60)
    print("This will build the container and deploy your app...")
    print("(First deployment may take 5-10 minutes to download models)\n")
    
    if not run_command(
        "modal deploy modal_handler.py",
        "Deploying application"
    ):
        print("\n⚠️ Deployment failed.")
        return
    
    # Success!
    print("\n" + "=" * 60)
    print("🎉 DEPLOYMENT SUCCESSFUL!")
    print("=" * 60)
    
    print("\n📋 Next Steps:")
    print("1. Copy your endpoint URL from the output above")
    print("2. Update test_modal.py with your endpoint URL")
    print("3. Run: python test_modal.py")
    print("\n💡 View logs: modal logs ai-image-checker")
    print("💡 Visit dashboard: https://modal.com/apps")


if __name__ == "__main__":
    main()
