from pathlib import Path

main = Path("android/app/src/main/kotlin/com/andreadada/pptx_to_pdf/MainActivity.kt")
main.parent.mkdir(parents=True, exist_ok=True)
main.write_text(r'''package com.andreadada.pptx_to_pdf

import android.graphics.*
import android.graphics.pdf.PdfDocument
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.w3c.dom.Element
import java.io.*
import java.util.zip.ZipFile
import javax.xml.parsers.DocumentBuilderFactory

class MainActivity : FlutterActivity() {
    private val channel = "com.andreadada.pptx_to_pdf/converter"
    override fun configureFlutterEngine(engine: FlutterEngine) {
        super.configureFlutterEngine(engine)
        MethodChannel(engine.dartExecutor.binaryMessenger, channel).setMethodCallHandler { call, result ->
            if (call.method != "convertPptxToPdf") { result.notImplemented(); return@setMethodCallHandler }
            val path = call.argument<String>("inputPath")
            val name = call.argument<String>("fileName") ?: "presentation.pptx"
            if (path == null) { result.error("INPUT","File PPTX non valido",null); return@setMethodCallHandler }
            Thread {
                try {
                    val out = PptxRenderer(File(path)).render(File(getExternalFilesDir(null) ?: filesDir,
                        name.replace(Regex("\\.pptx$", RegexOption.IGNORE_CASE), ".pdf")))
                    runOnUiThread { result.success(out.absolutePath) }
                } catch (t: Throwable) {
                    runOnUiThread { result.error("CONVERT", t.message ?: t.javaClass.simpleName, null) }
                }
            }.start()
        }
    }
}

private class PptxRenderer(private val file: File) {
    private val dbf = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }
    private val emuPerPoint = 12700.0
    private fun xml(zip: ZipFile, name: String) = zip.getEntry(name)?.let { e -> zip.getInputStream(e).use { dbf.newDocumentBuilder().parse(it) } }
    private fun attr(e: Element, n: String): Long = e.getAttribute(n).toLongOrNull() ?: 0L
    private fun descendants(e: Element, local: String): List<Element> {
        val n=e.getElementsByTagNameNS("*",local); return (0 until n.length).mapNotNull { n.item(it) as? Element }
    }
    private fun xfrm(shape: Element): FloatArray {
        val x=descendants(shape,"xfrm").firstOrNull() ?: return floatArrayOf(0f,0f,0f,0f)
        val off=descendants(x,"off").firstOrNull(); val ext=descendants(x,"ext").firstOrNull()
        return floatArrayOf((off?.let{attr(it,"x")}?:0)/emuPerPoint.toFloat(),(off?.let{attr(it,"y")}?:0)/emuPerPoint.toFloat(),
            (ext?.let{attr(it,"cx")}?:0)/emuPerPoint.toFloat(),(ext?.let{attr(it,"cy")}?:0)/emuPerPoint.toFloat())
    }
    private fun color(el: Element, fallback: Int): Int {
        val srgb=descendants(el,"srgbClr").firstOrNull()?.getAttribute("val")
        return try { if(!srgb.isNullOrBlank()) Color.parseColor("#$srgb") else fallback } catch(_:Throwable){fallback}
    }
    private fun rels(zip: ZipFile, slideNo: Int): Map<String,String> {
        val d=xml(zip,"ppt/slides/_rels/slide$slideNo.xml.rels") ?: return emptyMap()
        val out=mutableMapOf<String,String>(); val n=d.getElementsByTagNameNS("*","Relationship")
        for(i in 0 until n.length){ val e=n.item(i) as Element; var t=e.getAttribute("Target")
            if(t.startsWith("../")) t="ppt/"+t.removePrefix("../") else if(!t.startsWith("ppt/")) t="ppt/slides/$t"
            out[e.getAttribute("Id")]=t
        }; return out
    }
    fun render(output: File): File {
        ZipFile(file).use { zip ->
            val pres=xml(zip,"ppt/presentation.xml") ?: error("PPTX non valido")
            val sldSz=pres.getElementsByTagNameNS("*","sldSz").item(0) as? Element
            val wPt=((sldSz?.let{attr(it,"cx")}?:12192000)/emuPerPoint).toInt().coerceAtLeast(1)
            val hPt=((sldSz?.let{attr(it,"cy")}?:6858000)/emuPerPoint).toInt().coerceAtLeast(1)
            val slideEntries=zip.entries().asSequence().map{it.name}.filter{Regex("""ppt/slides/slide\d+\.xml""").matches(it)}
                .sortedBy{Regex("""\d+""").find(it)?.value?.toInt()?:0}.toList()
            val pdf=PdfDocument()
            slideEntries.forEachIndexed { idx, path ->
                val doc=xml(zip,path) ?: return@forEachIndexed
                val page=pdf.startPage(PdfDocument.PageInfo.Builder(wPt,hPt,idx+1).create())
                val c=page.canvas; c.drawColor(Color.WHITE)
                val slideNo=Regex("""\d+""").find(path)?.value?.toInt()?:idx+1
                val relationships=rels(zip,slideNo)
                val spTree=doc.getElementsByTagNameNS("*","spTree").item(0) as? Element
                if(spTree!=null) {
                    for(i in 0 until spTree.childNodes.length) {
                        val node=spTree.childNodes.item(i); if(node !is Element) continue
                        when(node.localName) {
                            "sp" -> drawShape(c,node)
                            "pic" -> drawPicture(c,node,zip,relationships)
                            "graphicFrame" -> drawTable(c,node)
                        }
                    }
                }
                pdf.finishPage(page)
            }
            FileOutputStream(output).use { pdf.writeTo(it) }; pdf.close()
        }
        return output
    }
    private fun drawShape(c: Canvas, s: Element) {
        val a=xfrm(s); if(a[2]<=0 || a[3]<=0) return
        val fill=color(descendants(s,"solidFill").firstOrNull()?:s,Color.TRANSPARENT)
        if(fill!=Color.TRANSPARENT) c.drawRect(a[0],a[1],a[0]+a[2],a[1]+a[3],Paint(Paint.ANTI_ALIAS_FLAG).apply{color=fill})
        val paras=descendants(s,"p"); if(paras.isEmpty()) return
        var y=a[1]+18f
        for(p in paras) {
            val runs=descendants(p,"r"); val texts=if(runs.isEmpty()) descendants(p,"t") else runs.flatMap{descendants(it,"t")}
            val line=texts.joinToString(""){it.textContent}; if(line.isBlank()){y+=14f;continue}
            val rPr=descendants(p,"rPr").firstOrNull() ?: descendants(s,"defRPr").firstOrNull()
            val size=(rPr?.getAttribute("sz")?.toFloatOrNull()?.div(100f)?:18f).coerceIn(6f,80f)
            val paint=Paint(Paint.ANTI_ALIAS_FLAG).apply{color=rPr?.let{color(it,Color.BLACK)}?:Color.BLACK;textSize=size}
            val words=line.split(" "); var current=""; val maxW=a[2].coerceAtLeast(20f)
            for(word in words) {
                val test=if(current.isEmpty()) word else "$current $word"
                if(paint.measureText(test)>maxW && current.isNotEmpty()){ c.drawText(current,a[0],y,paint); y+=size*1.25f; current=word } else current=test
            }
            if(current.isNotEmpty()){c.drawText(current,a[0],y,paint);y+=size*1.25f}
        }
    }
    private fun drawPicture(c: Canvas, p: Element, zip: ZipFile, rel: Map<String,String>) {
        val a=xfrm(p); val blip=descendants(p,"blip").firstOrNull()?:return
        var id=""; for(i in 0 until blip.attributes.length){val n=blip.attributes.item(i);if(n.localName=="embed")id=n.nodeValue}
        val target=rel[id]?:return; val entry=zip.getEntry(target)?:return
        val bmp=zip.getInputStream(entry).use{BitmapFactory.decodeStream(it)}?:return
        c.drawBitmap(bmp,null,RectF(a[0],a[1],a[0]+a[2],a[1]+a[3]),Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)); bmp.recycle()
    }
    private fun drawTable(c: Canvas, g: Element) {
        val a=xfrm(g); val rows=descendants(g,"tr"); if(rows.isEmpty()) return
        val rh=a[3]/rows.size.coerceAtLeast(1); var y=a[1]
        for(row in rows){val cells=descendants(row,"tc");val cw=a[2]/cells.size.coerceAtLeast(1);var x=a[0]
            for(cell in cells){c.drawRect(x,y,x+cw,y+rh,Paint().apply{style=Paint.Style.STROKE;color=Color.GRAY})
                val text=descendants(cell,"t").joinToString(""){it.textContent};c.drawText(text.take(80),x+4,y+16,Paint(Paint.ANTI_ALIAS_FLAG).apply{color=Color.BLACK;textSize=12f});x+=cw};y+=rh}
    }
}
''')
