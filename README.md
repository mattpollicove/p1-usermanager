This README is generated based on the initial public release of the code except for this introduction. Obviously there are a lot of places this project can go. 
I went for a basic UI with nothing too flashy just to establish the project. There are a lot of places I'd like to take this, but I'm also interrested to see what other 
people would like to do with this application. The sky's the limit to be sure!

PingOne UserManager (v1.3.1)
UserManager is a robust, cross-platform desktop application designed for IT administrators to manage PingOne identity environments. It simplifies complex administrative tasks like bulk user deletion, nested attribute editing, and environment synchronization through a clean, multi-threaded GUI.

🚀 Key Features
Multi-Profile Support: Manage multiple PingOne environments (Dev, Staging, Prod) with easy switching.

Hardware-Backed Security: Sensitive Client Secrets are never stored in plain text; they are vaulted in the OS-native keychain (Windows Credential Manager, macOS Keychain, or Linux Secret Service).

Dynamic Attribute Editor: A recursive JSON editor that flattens nested PingOne identity objects for easy modification.

Delta-Patching: Updates are sent via HTTP PATCH, sending only the fields you changed to preserve data integrity.

Bulk Operations: Select and delete multiple users simultaneously with a safe, queued background worker.

Live Statistics: Real-time dashboard showing total user and population counts.

🛠️ Technical Architecture
The application uses a Non-Blocking Worker Pattern. All API communications are handled by QRunnable workers in a dedicated thread pool, ensuring the interface remains responsive even when fetching thousands of users.

📋 Prerequisites
Python 3.9 or higher

A PingOne Environment ID

A Worker App with Client Credentials grant type and sufficient Roles (e.g., Identity Admin).

📥 Installation
Clone the repository:

Bash
git clone https://github.com/your-org/pingone-usermanager.git
cd pingone-usermanager
Create a virtual environment:

Bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Install dependencies:

Bash
pip install pyside6 httpx keyring
🚦 Getting Started
Launch the App:

Bash
python usermanager.py
Configure a Profile:

Navigate to the Configuration tab.

Enter your Environment ID, Client ID, and Client Secret.

Click Save Profile.

Sync Data:

Click Connect & Sync. The app will fetch your population mapping and user list.

Manage Users:

Double-click a row to edit a user's full attribute set.

Use Ctrl+Click or Shift+Click to select multiple users for deletion.
