"""
Predetermined chat messages for the DataVerse Agent Dashboard.
Centralizing messages here keeps the main dashboard file clean and makes
it easy to add, edit, or translate messages in one place.
"""

INTRO_MESSAGES = [
    "👋 Hey there! I'm your DataVerse Analyst. Upload a CSV file and let's uncover some insights together!",
    "🚀 Welcome to DataVerse! Ready to turn your data into stunning visualizations? Start by uploading a CSV file.",
    "📊 Hi! I'm here to help you explore and visualize your data. Drop a CSV file to get started!",
    "🔍 Hello! Let's dive into your data. Upload a CSV file and I'll help you discover patterns and trends.",
    "✨ Welcome! I'm your data exploration assistant. Share a CSV file and let's create some amazing dashboards!",
    "💡 Hey! Ready to make sense of your data? Upload a CSV file and we'll get started right away.",
    "🎯 Hi there! I specialize in turning raw data into actionable insights. Upload a CSV to begin!",
]

NO_CSV_MESSAGES = [
    "📂 It looks like you haven't uploaded a dataset yet. Please attach a CSV file so I can start analyzing!",
    "⚠️ I need data to work with! Please upload a CSV file along with your message.",
    "🗂️ No dataset detected. Drop a CSV file in the chat and I'll get right on it!",
    "📎 Before I can help, I'll need some data. Please upload a CSV file to continue.",
]

SESSION_RESUMED_MESSAGES = [
    "👋 Welcome back! Let's pick up right where we left off.",
    "🔄 Session restored! Your previous data and conversation are ready.",
    "📂 Back to this session — all your history is intact. How can I help?",
    "✨ Resumed! Your charts and data are still here. What's next?",
    "🎯 Session loaded successfully. Ready to continue the analysis!",
]
