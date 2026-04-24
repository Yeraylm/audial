/* ============================================================
   Sistema de internacionalizacion ES / EN
   ============================================================ */

const TRANSLATIONS = {
  es: {
    'nav.upload':            'Ingestar',
    'nav.conversations':     'Conversaciones',
    'nav.dashboard':         'Dashboard',
    'nav.chat':              'Asistente',
    'nav.api':               'API',

    'hero.badge':            '100% local · sin cloud · sin GPU obligatoria',
    'hero.title.pre':        'Transforma',
    'hero.title.mid':        'horas de audio',
    'hero.title.post':       'en',
    'hero.title.italic':     'conocimiento estructurado',
    'hero.sub':              'Transcripción, análisis semántico avanzado, búsqueda vectorial y asistente conversacional con modelos de IA ejecutándose íntegramente en tu PC.',

    'upload.dropzone.title':    'Arrastra tu audio aquí',
    'upload.dropzone.formats':  'mp3 · wav · m4a · ogg · flac · hasta 200 MB',
    'upload.dropzone.button':   'Seleccionar archivo',
    'upload.lang.label':        'Idioma del audio',
    'upload.lang.auto':         'Detección automática',
    'upload.lang.es':           'Español',
    'upload.lang.en':           'Inglés',

    'stage.transcription':  'Transcripción',
    'stage.diarization':    'Hablantes',
    'stage.llm_analysis':   'Análisis IA',
    'stage.embeddings':     'Indexado',
    'stage.done':           'Completo',

    'features.whisper.title': 'Whisper local',
    'features.whisper.desc':  'faster-whisper en CPU con VAD y timestamps para transcribir sin límites de privacidad.',
    'features.diar.title':    'Diarización',
    'features.diar.desc':     'Identificación automática de hablantes con embeddings de voz y clustering aglomerativo.',
    'features.llm.title':     'LLM local',
    'features.llm.desc':      'Llama 3, Mistral o Qwen vía Ollama — 14+ extracciones estructuradas sin internet.',
    'features.rag.title':     'Búsqueda RAG',
    'features.rag.desc':      'Embeddings multilingües indexados en Chroma para recuperación semántica precisa.',

    'bigdata.label':          'Arquitectura',
    'bigdata.title.pre':      'Big Data',
    'bigdata.title.italic':   'Medallion',
    'bigdata.title.post':     'en tu máquina',
    'bigdata.desc':           'Capas Bronze, Silver y Gold inmutables. Escala a miles de audios con multiprocessing y migrable a PySpark sin reescribir el pipeline.',
    'bigdata.bronze.desc':    'Audios crudos · manifest parquet',
    'bigdata.silver.desc':    'Transcripciones · diarización · limpieza',
    'bigdata.gold.desc':      'Analysis estructurado · agregados BI',

    'conv.label':        'Tus audios',
    'conv.title':        'Conversaciones',
    'conv.refresh':      'Actualizar',
    'conv.empty.title':  'Aún no hay conversaciones',
    'conv.empty.desc':   'Sube tu primer audio para comenzar el análisis',
    'conv.empty.cta':    'Subir primer audio',
    'conv.badge.done':   'procesado',
    'conv.badge.running':'procesando',
    'conv.badge.failed': 'fallido',
    'conv.badge.pending':'en cola',

    'detail.back':          'Conversaciones',
    'detail.title':         'Análisis completo',
    'detail.unavail.title': 'Análisis no disponible',
    'detail.unavail.desc':  'Este audio puede estar todavía procesándose o el job habrá fallado.',
    'detail.unavail.back':  'Volver',

    'tab.summary':    'Resumen',
    'tab.transcript': 'Transcripción',
    'tab.entities':   'Entidades',
    'tab.tasks':      'Tareas',
    'tab.sentiment':  'Sentimiento',
    'tab.topics':     'Temas',
    'tab.timeline':   'Timeline',
    'tab.metrics':    'Métricas',
    'tab.related':    'Relacionados',

    'summary.tldr':       'TL;DR',
    'summary.medium':     'Resumen ejecutivo',
    'summary.long':       'Resumen completo',
    'transcript.search':  'Buscar en la transcripción…',
    'transcript.count':   'segmentos',

    'tasks.title':      'Tareas',
    'decisions.title':  'Decisiones',
    'questions.title':  'Preguntas',
    'tasks.empty':      'Sin tareas detectadas.',
    'decisions.empty':  'Sin decisiones detectadas.',
    'questions.empty':  'Sin preguntas detectadas.',

    'sentiment.evo':     'Evolución temporal',
    'sentiment.speaker': 'Por hablante',
    'sentiment.empty':   'Sin conflictos detectados.',
    'conflicts.title':   'Conflictos detectados',

    'topics.main':       'Temas principales',
    'topics.intents':    'Intenciones detectadas',
    'topics.empty':      'Sin temas detectados.',
    'intents.empty':     'Sin intenciones detectadas.',

    'timeline.empty':    'Sin eventos detectados.',

    'metrics.participation': 'Participación por hablante',
    'metrics.stats':         'Estadísticas',
    'metrics.duration':      'Duración total',
    'metrics.segments':      'Nº de segmentos',
    'metrics.speakers':      'Nº de hablantes',
    'metrics.avg':           'Segmento medio',
    'metrics.wpm':           'Palabras / minuto',

    'related.empty':     'Sin audios relacionados todavía.',

    'dashboard.label':    'Analítica global',
    'dashboard.title':    'Dashboard',
    'dashboard.kpi.audios':    'Audios',
    'dashboard.kpi.analyses':  'Analizados',
    'dashboard.kpi.hours':     'Horas procesadas',
    'dashboard.kpi.tasks':     'Tareas extraídas',
    'dashboard.chart.sentiment':'Distribución de sentimiento',
    'dashboard.chart.totals':   'Totales extraídos',

    'chat.label':        'RAG local',
    'chat.title':        'Asistente sobre tus audios',
    'chat.sub':          'Respuestas ancladas exclusivamente en tus transcripciones. Ningún dato sale de tu equipo.',
    'chat.welcome.hi':   'Hola, soy',
    'chat.welcome.desc': 'Pregúntame sobre tus audios. Resumo, extraigo, comparo y cito las fuentes exactas.',
    'chat.sugg.1':       '¿Cuáles fueron las decisiones clave?',
    'chat.sugg.2':       'Resume la conversación en 3 puntos',
    'chat.sugg.3':       '¿Qué tareas quedaron pendientes?',
    'chat.placeholder':  'Escribe tu pregunta…',
    'chat.all':          'Todas las conversaciones',

    'footer':            'Audial · Plataforma IA Conversacional · Procesamiento 100% local · TFM 2026',
  },

  en: {
    'nav.upload':            'Ingest',
    'nav.conversations':     'Conversations',
    'nav.dashboard':         'Dashboard',
    'nav.chat':              'Assistant',
    'nav.api':               'API',

    'hero.badge':            '100% local · no cloud · no required GPU',
    'hero.title.pre':        'Turn',
    'hero.title.mid':        'hours of audio',
    'hero.title.post':       'into',
    'hero.title.italic':     'structured knowledge',
    'hero.sub':              'Transcription, advanced semantic analysis, vector search and a conversational assistant with AI models running entirely on your PC.',

    'upload.dropzone.title':    'Drop your audio here',
    'upload.dropzone.formats':  'mp3 · wav · m4a · ogg · flac · up to 200 MB',
    'upload.dropzone.button':   'Select file',
    'upload.lang.label':        'Audio language',
    'upload.lang.auto':         'Auto-detect',
    'upload.lang.es':           'Spanish',
    'upload.lang.en':           'English',

    'stage.transcription':  'Transcription',
    'stage.diarization':    'Speakers',
    'stage.llm_analysis':   'AI analysis',
    'stage.embeddings':     'Indexing',
    'stage.done':           'Done',

    'features.whisper.title': 'Local Whisper',
    'features.whisper.desc':  'faster-whisper on CPU with VAD and timestamps for private, unlimited transcription.',
    'features.diar.title':    'Diarization',
    'features.diar.desc':     'Automatic speaker identification via voice embeddings and agglomerative clustering.',
    'features.llm.title':     'Local LLM',
    'features.llm.desc':      'Llama 3, Mistral or Qwen via Ollama — 14+ structured extractions without internet.',
    'features.rag.title':     'RAG search',
    'features.rag.desc':      'Multilingual embeddings indexed in Chroma for precise semantic retrieval.',

    'bigdata.label':          'Architecture',
    'bigdata.title.pre':      'Big Data',
    'bigdata.title.italic':   'Medallion',
    'bigdata.title.post':     'on your machine',
    'bigdata.desc':           'Immutable Bronze, Silver and Gold layers. Scales to thousands of audios with multiprocessing and is portable to PySpark without rewriting the pipeline.',
    'bigdata.bronze.desc':    'Raw audios · parquet manifest',
    'bigdata.silver.desc':    'Transcripts · diarization · cleaning',
    'bigdata.gold.desc':      'Structured analysis · BI aggregates',

    'conv.label':        'Your audios',
    'conv.title':        'Conversations',
    'conv.refresh':      'Refresh',
    'conv.empty.title':  'No conversations yet',
    'conv.empty.desc':   'Upload your first audio to start the analysis',
    'conv.empty.cta':    'Upload first audio',
    'conv.badge.done':   'processed',
    'conv.badge.running':'processing',
    'conv.badge.failed': 'failed',
    'conv.badge.pending':'queued',

    'detail.back':          'Conversations',
    'detail.title':         'Complete analysis',
    'detail.unavail.title': 'Analysis not available',
    'detail.unavail.desc':  'This audio may still be processing or the job may have failed.',
    'detail.unavail.back':  'Go back',

    'tab.summary':    'Summary',
    'tab.transcript': 'Transcript',
    'tab.entities':   'Entities',
    'tab.tasks':      'Tasks',
    'tab.sentiment':  'Sentiment',
    'tab.topics':     'Topics',
    'tab.timeline':   'Timeline',
    'tab.metrics':    'Metrics',
    'tab.related':    'Related',

    'summary.tldr':       'TL;DR',
    'summary.medium':     'Executive summary',
    'summary.long':       'Full summary',
    'transcript.search':  'Search in the transcript…',
    'transcript.count':   'segments',

    'tasks.title':      'Tasks',
    'decisions.title':  'Decisions',
    'questions.title':  'Questions',
    'tasks.empty':      'No tasks detected.',
    'decisions.empty':  'No decisions detected.',
    'questions.empty':  'No questions detected.',

    'sentiment.evo':     'Temporal evolution',
    'sentiment.speaker': 'By speaker',
    'sentiment.empty':   'No conflicts detected.',
    'conflicts.title':   'Conflicts detected',

    'topics.main':       'Main topics',
    'topics.intents':    'Detected intents',
    'topics.empty':      'No topics detected.',
    'intents.empty':     'No intents detected.',

    'timeline.empty':    'No events detected.',

    'metrics.participation': 'Participation by speaker',
    'metrics.stats':         'Statistics',
    'metrics.duration':      'Total duration',
    'metrics.segments':      '# of segments',
    'metrics.speakers':      '# of speakers',
    'metrics.avg':           'Average segment',
    'metrics.wpm':           'Words / minute',

    'related.empty':     'No related audios yet.',

    'dashboard.label':    'Global analytics',
    'dashboard.title':    'Dashboard',
    'dashboard.kpi.audios':    'Audios',
    'dashboard.kpi.analyses':  'Analyzed',
    'dashboard.kpi.hours':     'Hours processed',
    'dashboard.kpi.tasks':     'Tasks extracted',
    'dashboard.chart.sentiment':'Sentiment distribution',
    'dashboard.chart.totals':   'Totals extracted',

    'chat.label':        'Local RAG',
    'chat.title':        'Assistant over your audios',
    'chat.sub':          'Answers grounded exclusively in your transcripts. Nothing leaves your machine.',
    'chat.welcome.hi':   "Hi, I'm",
    'chat.welcome.desc': 'Ask me anything about your audios. I summarize, extract, compare and cite exact sources.',
    'chat.sugg.1':       'What were the key decisions?',
    'chat.sugg.2':       'Summarize the conversation in 3 points',
    'chat.sugg.3':       'Which tasks are still pending?',
    'chat.placeholder':  'Type your question…',
    'chat.all':          'All conversations',

    'footer':            'Audial · Conversational AI Platform · 100% local processing · TFM 2026',
  }
};

// Idioma actual (persistente)
let currentLang = localStorage.getItem('audial_lang')
  || (navigator.language?.startsWith('en') ? 'en' : 'es');

function t(key) {
  return TRANSLATIONS[currentLang]?.[key] || TRANSLATIONS.es[key] || key;
}

function applyTranslations() {
  document.documentElement.lang = currentLang;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const val = t(key);
    if (val) el.textContent = val;
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.dataset.i18nPlaceholder;
    const val = t(key);
    if (val) el.setAttribute('placeholder', val);
  });
  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    const key = el.dataset.i18nHtml;
    const val = t(key);
    if (val) el.innerHTML = val;
  });
  // Actualizar botones de idioma
  document.querySelectorAll('[data-lang-btn]').forEach(b => {
    b.classList.toggle('active', b.dataset.langBtn === currentLang);
  });
}

function setLang(lang) {
  if (!TRANSLATIONS[lang]) return;
  currentLang = lang;
  localStorage.setItem('audial_lang', lang);
  applyTranslations();
  window.dispatchEvent(new CustomEvent('langchange', { detail: lang }));
}

// Exportar globalmente
window.i18n = { t, setLang, applyTranslations, get lang() { return currentLang; } };

// Aplicar al cargar
document.addEventListener('DOMContentLoaded', applyTranslations);
