# PPTX to PDF

Flutter Android app for converting PowerPoint `.pptx` files to PDF through a LibreOffice backend.

## Android build

GitHub Actions builds a release APK on every push to `main` and on manual dispatch.

The APK is available from the workflow run as the `pptx-to-pdf-apk` artifact.

## Backend

```bash
cd backend
docker build -t pptx-to-pdf-api .
docker run -p 8080:8080 pptx-to-pdf-api
```

For a production APK, build with your HTTPS backend URL:

```bash
flutter build apk --release --dart-define=CONVERTER_API=https://your-host/convert
```
