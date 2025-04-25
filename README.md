# KeyGo - URL Bookmarker

A simple web application to save and quickly access your favorite websites using custom shortcut names.

## Features

- Create custom shortcuts to websites
- Search and access your shortcuts instantly
- Track visit counts for each shortcut
- Add notes to your shortcuts
- Dark mode support
- MongoDB integration for data storage

## Setup

### Prerequisites

- Python 3.7+
- MongoDB Atlas account (or local MongoDB server)

### Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd keygo
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your MongoDB connection:
   - Create a `.env` file in the project root directory
   - Add your MongoDB connection string:
     ```
     MONGODB_URI="mongodb+srv://username:password@your-cluster.mongodb.net/?retryWrites=true&w=majority"
     DB_NAME="keygo_bookmarks"
     COLLECTION_NAME="bookmarks"
     FLASK_APP=app.py
     FLASK_ENV=development
     ```

4. Run the application:
   ```
   flask run
   ```

5. Access the application at `http://localhost:5000`

## Usage

- **Home Page**: Search for a shortcut
- **Add Page**: Create a new shortcut
- **Shortcuts Page**: View and manage all your shortcuts
- **Edit Page**: Modify existing shortcuts

## MongoDB Integration

This application uses MongoDB Atlas for data storage. The data structure in MongoDB is as follows:

```
{
  "_id": ObjectId("..."),
  "name": "shortcut_name",
  "url": "https://example.com",
  "notes": "Optional notes",
  "date_added": "YYYY-MM-DD HH:MM:SS",
  "date_modified": "YYYY-MM-DD HH:MM:SS",
  "visits": 0
}
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Author

- Nandeesh PS
- GitHub: [Nandeeshps-coder](https://github.com/Nandeeshps-coder) 