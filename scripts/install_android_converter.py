from pathlib import Path

gradle = Path("android/app/build.gradle.kts")
s = gradle.read_text()
needle = "dependencies {"
deps = """dependencies {
    implementation("org.apache.poi:poi-ooxml:5.4.1")
    implementation("org.apache.pdfbox:pdfbox:3.0.5")
"""
if needle in s:
    s = s.replace(needle, deps, 1)
else:
    s += "\n" + deps + "}\n"
gradle.write_text(s)

main = Path("android/app/src/main/kotlin/com/andreadada/pptx_to_pdf/MainActivity.kt")
main.parent.mkdir(parents=True, exist_ok=True)
main.write_text(r'''package com.andreadada.pptx_to_pdf

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.pdf.PdfDocument
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.apache.poi.xslf.usermodel.XMLSlideShow
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream

class MainActivity : FlutterActivity() {
    private val channel = "com.andreadada.pptx_to_pdf/converter"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channel).setMethodCallHandler { call, result ->
            if (call.method != "convertPptxToPdf") {
                result.notImplemented()
                return@setMethodCallHandler
            }
            val inputPath = call.argument<String>("inputPath")
            val fileName = call.argument<String>("fileName") ?: "presentation.pptx"
            if (inputPath == null) {
                result.error("INPUT", "File PPTX non valido", null)
                return@setMethodCallHandler
            }
            Thread {
                try {
                    val output = convert(File(inputPath), fileName)
                    runOnUiThread { result.success(output.absolutePath) }
                } catch (t: Throwable) {
                    runOnUiThread { result.error("CONVERT", t.message ?: t.javaClass.simpleName, null) }
                }
            }.start()
        }
    }

    private fun convert(input: File, fileName: String): File {
        val outName = fileName.replace(Regex("\\.pptx$", RegexOption.IGNORE_CASE), ".pdf")
        val output = File(getExternalFilesDir(null) ?: filesDir, outName)
        FileInputStream(input).use { stream ->
            XMLSlideShow(stream).use { ppt ->
                val size = ppt.pageSize
                val pdf = PdfDocument()
                try {
                    val scale = 2.0
                    val width = (size.width * scale).toInt().coerceAtLeast(1)
                    val height = (size.height * scale).toInt().coerceAtLeast(1)
                    ppt.slides.forEachIndexed { index, slide ->
                        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
                        val canvas = Canvas(bitmap)
                        canvas.drawColor(android.graphics.Color.WHITE)
                        // POI XSLF rendering is Java2D-based. Android does not provide java.awt.Graphics2D.
                        // The next adapter layer is installed separately; fail explicitly instead of uploading data.
                        throw UnsupportedOperationException("XSLF Java2D rich rendering adapter not yet available on Android runtime")
                    }
                    FileOutputStream(output).use { pdf.writeTo(it) }
                } finally {
                    pdf.close()
                }
            }
        }
        return output
    }
}
''')
