import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:open_filex/open_filex.dart';
import 'package:share_plus/share_plus.dart';

void main() => runApp(const ConverterApp());

class ConverterApp extends StatelessWidget {
  const ConverterApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.indigo),
        home: const HomePage(),
      );
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  PlatformFile? input;
  File? output;
  bool busy = false;
  String? error;

  static const apiUrl = String.fromEnvironment(
    'CONVERTER_API',
    defaultValue: 'http://10.0.2.2:8080/convert',
  );

  Future<void> pick() async {
    final r = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pptx'],
    );
    if (r != null) {
      setState(() {
        input = r.files.single;
        output = null;
        error = null;
      });
    }
  }

  Future<void> convert() async {
    if (input?.path == null) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final req = http.MultipartRequest('POST', Uri.parse(apiUrl));
      req.files.add(await http.MultipartFile.fromPath(
        'file',
        input!.path!,
        filename: input!.name,
      ));
      final res = await req.send();
      if (res.statusCode != 200) {
        throw Exception('Conversione fallita (${res.statusCode})');
      }
      final bytes = await res.stream.toBytes();
      final dir = await getApplicationDocumentsDirectory();
      final name = input!.name.replaceFirst(
        RegExp(r'\.pptx$', caseSensitive: false),
        '.pdf',
      );
      final f = File('${dir.path}/$name');
      await f.writeAsBytes(bytes, flush: true);
      setState(() => output = f);
    } catch (e) {
      setState(() => error = e.toString());
    } finally {
      setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('PPTX → PDF')),
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 560),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.picture_as_pdf_rounded,
                      size: 76,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'Converti PowerPoint in PDF',
                      style:
                          TextStyle(fontSize: 26, fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Seleziona un file .pptx. Il documento viene convertito mantenendo il layout delle slide.',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 28),
                    Card(
                      child: ListTile(
                        leading: const Icon(Icons.slideshow_rounded),
                        title: Text(
                            input?.name ?? 'Nessun PowerPoint selezionato'),
                        subtitle: input == null
                            ? null
                            : Text(
                                '${(input!.size / 1024 / 1024).toStringAsFixed(2)} MB'),
                        trailing: TextButton(
                          onPressed: busy ? null : pick,
                          child: Text(input == null ? 'Scegli' : 'Cambia'),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: FilledButton.icon(
                        onPressed: input == null || busy ? null : convert,
                        icon: busy
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.sync_alt),
                        label:
                            Text(busy ? 'Conversione…' : 'Converti in PDF'),
                      ),
                    ),
                    if (error != null) ...[
                      const SizedBox(height: 14),
                      Text(
                        error!,
                        style: TextStyle(
                            color: Theme.of(context).colorScheme.error),
                        textAlign: TextAlign.center,
                      ),
                    ],
                    if (output != null) ...[
                      const SizedBox(height: 22),
                      const Divider(),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: () => OpenFilex.open(output!.path),
                              icon: const Icon(Icons.open_in_new),
                              label: const Text('Apri PDF'),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: () =>
                                  Share.shareXFiles([XFile(output!.path)]),
                              icon: const Icon(Icons.share),
                              label: const Text('Condividi'),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      );
}
