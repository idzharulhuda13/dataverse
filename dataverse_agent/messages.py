"""
Predetermined chat messages for the DataVerse Agent Dashboard.
Centralizing messages here keeps the main dashboard file clean and makes
it easy to add, edit, or translate messages in one place.
"""

INTRO_MESSAGES = [
    "👋 Hey there! I'm your DataVerse Analyst. Upload a data file and let's uncover some insights together!",
    "🚀 Welcome to DataVerse! Ready to turn your data into stunning visualizations? Start by uploading a file — CSV, Excel, JSON, Parquet, or TSV.",
    "📊 Hi! I'm here to help you explore and visualize your data. Drop a file to get started!",
    "🔍 Hello! Let's dive into your data. Upload a CSV, Excel, or any supported file and I'll help you discover patterns.",
    "✨ Welcome! I'm your data exploration assistant. Share a data file and let's create some amazing dashboards!",
    "💡 Hey! Ready to make sense of your data? Upload a file and we'll get started right away.",
    "🎯 Hi there! I specialize in turning raw data into actionable insights. Upload a data file to begin!",
]

NO_CSV_MESSAGES = [
    "📂 It looks like you haven't uploaded a dataset yet. Please attach a data file (CSV, Excel, JSON, Parquet, or TSV) so I can start analyzing!",
    "⚠️ I need data to work with! Please upload a data file along with your message.",
    "🗂️ No dataset detected. Drop a data file in the chat and I'll get right on it!",
    "📎 Before I can help, I'll need some data. Please upload a supported file to continue.",
]

SESSION_RESUMED_MESSAGES = [
    "👋 Welcome back! Let's pick up right where we left off.",
    "🔄 Session restored! Your previous data and conversation are ready.",
    "📂 Back to this session — all your history is intact. How can I help?",
    "✨ Resumed! Your charts and data are still here. What's next?",
    "🎯 Session loaded successfully. Ready to continue the analysis!",
]

UPLOAD_LANDING_MESSAGES = [
    "📂 **Drop your data file here** to get started — CSV, Excel, JSON, Parquet, or TSV. I'll analyze it and suggest the most valuable insights right away.",
    "🚀 **Upload a data file** and I'll instantly scan your dataset to recommend the best analyses and visualizations.",
    "📊 **Start by uploading your data.** I support CSV, Excel, JSON, Parquet, and TSV. Once I see it, I'll tell you exactly what's worth exploring.",
]

ANALYZING_DATA_MESSAGES = [
    "🔍 Scanning your dataset and identifying key patterns...",
    "📊 Analyzing columns, distributions, and relationships...",
    "🧠 Reading your data and preparing insight recommendations...",
]

