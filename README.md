
# GitHub Webhook Event Processor & UI (`webhook-repo`)

This project is a **Flask-based** application designed to receive, process, and store GitHub webhook events (**Push**, **Pull Request**, **Merge**) into a **MongoDB** database. It also provides a **simple UI** that polls the database every 15 seconds to display the latest repository changes.

> 📌 This repository (`webhook-repo`) contains the webhook receiver and the frontend UI. It is intended to be used alongside another GitHub repository (referred to as `action-repo`) where Git operations occur.

---

## ✨ Features

- **Webhook Receiver**: Securely listens for incoming GitHub webhook events.
- **Event Processing**: Parses relevant info from `Push`, `Pull Request (opened)`, and `Merge (closed & merged)` events.
- **MongoDB Integration**: Stores event data into MongoDB.
- **Real-Time UI Updates**: A simple UI polls backend every 15 seconds.
- **Configurable**: Uses `.env` for MongoDB URI and webhook secret.
- **Structured Logging**: Logs incoming events and processing status.

---

## 🧱 Tech Stack

- **Backend**: Python, Flask
- **Database**: MongoDB (via Flask-PyMongo)
- **Frontend**: HTML, CSS, JavaScript (Vanilla)
- **Environment**: python-dotenv
- **Security**: HMAC-SHA256 Signature Verification

---

## 📁 Project Structure

```
webhook-repo/
├── app/
│   ├── __init__.py         # Application factory (create_app)
│   ├── extensions.py       # Flask extensions (e.g., PyMongo)
│   ├── webhook/            # Webhook logic
│   │   ├── __init__.py
│   │   └── routes.py       # Webhook endpoints
│   └── ui/                 # UI Blueprint
│       ├── __init__.py
│       ├── routes.py       # Serves index.html
│       └── templates/
│           └── index.html
│       └── static/
│           └── style.css
├── .env.example            # Template for environment config
├── requirements.txt        # Python dependencies
├── run.py                  # Entry point
└── README.md               # Project documentation
```

---

## ⚙️ Setup and Installation

### 1. Prerequisites

- Python 3.8+
- pip
- MongoDB (local or Atlas)
- Git
- [ngrok](https://ngrok.com/) (or similar for tunneling)

### 2. Clone the Repository

```bash
git clone https://github.com/spidyshivam/webhook-repo
cd webhook-repo
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create a `.env` file in the root directory and add:

```env
MONGO_URI="mongodb://localhost:27017/github_events"
GITHUB_WEBHOOK_SECRET="your_super_secret_webhook_token"
```

> 💡 Use your MongoDB URI if using Atlas (e.g., `mongodb+srv://...`)

### 6. Run the Application

```bash
python run.py
```

Visit:

- Web UI: [http://localhost:5000](http://localhost:5000)
- Webhook Endpoint: [http://localhost:5000/webhook/receiver](http://localhost:5000/webhook/receiver)

---

## 🔗 GitHub Webhook Setup (`action-repo`)

### 1. Expose Flask App

```bash
ngrok http 5000
```

Note the HTTPS URL (e.g., `https://abc123.ngrok.io`).

### 2. Add Webhook in GitHub

- Go to `Settings > Webhooks`
- Click **Add Webhook**
- **Payload URL**: `https://abc123.ngrok.io/webhook/receiver`
- **Content type**: `application/json`
- **Secret**: Same as `GITHUB_WEBHOOK_SECRET`
- **Events**: Select:
  - Push
  - Pull Request
- Click **Add Webhook**

> ✅ You should see a "ping" event logged in your Flask console.

---

## 🧾 MongoDB Schema

Events are stored in a collection (e.g., `events`) with:

```json
{
  "_id": ObjectId,
  "request_id": "abc123",               // Commit SHA or PR ID
  "author": "Travis",
  "action": "PUSH | PULL_REQUEST | MERGE",
  "from_branch": "dev",                 // null for push
  "to_branch": "main",
  "timestamp": "2021-04-01T12:00:00Z"   // UTC ISO 8601
}
```

---

## 🔌 API Endpoints

| Method | Route                 | Description                     |
|--------|----------------------|---------------------------------|
| POST   | `/webhook/receiver`  | GitHub sends webhook payloads   |
| GET    | `/webhook/events`    | UI fetches latest events        |
| GET    | `/`                  | Serves UI page (`index.html`)   |
| GET    | `/health`            | Health check                    |

---

## 👀 UI Display Formats

- **PUSH**:  
  `"Travis" pushed to "main" on 1st April 2021 - 9:30 PM UTC`

- **PULL_REQUEST**:  
  `"Travis" submitted a pull request from "dev" to "main" on 1st April 2021 - 9:00 AM UTC`

- **MERGE**:  
  `"Travis" merged branch "dev" to "main" on 2nd April 2021 - 12:00 PM UTC`

---

## ✅ How to Test

1. Ensure Flask app is running and ngrok is active.
2. Ensure webhook is properly added in `action-repo`.
3. Perform actions in `action-repo`:
   - Push commits
   - Open PRs
   - Merge PRs
4. Monitor Flask logs for event reception.
5. Open `http://localhost:5000` to see UI updating in real-time.

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
