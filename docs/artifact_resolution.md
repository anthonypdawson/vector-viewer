# Text Similarity Explanations — Product Requirements Document (PRD)

## 1. Overview
Vector Viewer needs to explain **why two text documents are similar** using natural language analysis. This goes beyond showing vector distances—it provides human-readable explanations of semantic similarity using local LLMs.

**Phase 1 Scope: Text-Only + Local Models First**
- Focus exclusively on text documents (covers 90%+ of use cases)
- Prioritize local/open-source models (privacy, cost, offline use)
- Cloud providers (OpenAI, Anthropic, Google) optional for Pro tier

The hybrid approach combines:

- Automatic text artifact resolution (best effort from metadata)
- Manual user‑provided text input (fallback)
- Local LLM explanations (primary)
- Cloud LLM explanations (optional premium)

## 2. Goals

### Primary Goals
- Explain text similarity using local LLMs (Ollama, llama.cpp, HuggingFace)
- Automatically extract text from vector DB metadata/documents
- Gracefully request user input when text is not accessible
- Zero API costs for core functionality
- Offline-first operation

### Secondary Goals
- Optional cloud LLM support (OpenAI, Anthropic, Google) for Pro tier
- Maintain provider‑agnostic architecture
- Support future modalities (images, audio) in later phases
- Preserve the forensic, artifact‑driven philosophy of the tool

## 3. Non‑Goals
- No attempt to reverse‑engineer embeddings
- No requirement to store or cache artifacts permanently
- No assumption that vector DBs contain complete or correct metadata
- No automatic downloading of unknown or unsafe URLs without user confirmation
- No multimodal support in Phase 1 (text-only for now)
- No dependency on paid cloud APIs for core features

## 4. User StoriesText Resolution
- As a user, when I select two similar documents, I want to see the original text automatically extracted from metadata or document fields.

### 4.2 Local Explanation
- As a user, I want similarity explanations using my local Ollama/LLaMA model without sending data to cloud APIs or incurring costs.

### 4.3 Manual Fallback
- As a user, if the text cannot be located, I want to see available metadata and paste/upload the missing text myself.

### 4.4 Optional Cloud Enhancement
- As a Pro user, I want the option to use GPT-4, Claude, or Gemini for higher-quality explanations when I'm willing to pay API costs.

### 4.5 Transparency
- As a user, I want to know which model was used, whether text was automatically resolved, and estimated API costs (if applicable)
### 4.4 Transparency
- As a user, I want to know how the Inspector determined the artifact type and whether it was automatically resolved or manually provided.

## 5. System Architecture

### 5.1 Text Artifact Resolver (new component)
Extracts text from vector database entries using a simple waterfall strategy:

#### Text Extraction Layers (in order)
1. **Direct document field**: Most vector DBs store text in a `document`, `text`, or `content` field
2. **Metadata inspection**: Check for `text`, `content`, `description`, `body` in metadata
3. **URL/path retrieval**: If metadata contains a file path or URL to .txt/.md/.json
4. **User input fallback**: Prompt user to paste text if none of above work

#### Output Example
```json
{
  "text": "The quick brown fox...",
  "source": "document_field",
  "confidence": 1.0
}
```

### 5.2 Local LLM Provider (primary)
Integrates with local inference engines:

**Supported Local Runtimes**
- **Ollama** (primary): Simple API, auto-downloads models, Mac/Windows/Linux
- **llama.cpp server** (secondary): Direct C++ inference, faster but more setup
- **HuggingFace Transformers** (tertiary): Python-native, works offline

**Example Local Models**
- `llama3.2:3b` - Fast, good quality (default)
- `mistral:7b` - Balanced speed/quality
- `qwen2.5:14b` - High quality, slower
- Any compatible model user has installed

### 5.3 Cloud LLM Provider (optional)
Optional integrations for Pro tier:

- **OpenAI**: GPT-4o, GPT-4-turbo (high quality, expensive)
- **Anthropic**: Claude 3.5 Sonnet (best reasoning)
- **Google**: Gemini 1.5 Pro (cost-effective)

User must provide API keys. Show estimated cost before each request.

### 5.4 Similarity Explanation Engine
Combines:

1. **Vector evidence**: Distance/similarity score from vector DB
2. **Text evidence**: LLM analysis of actual document content
3. **Metadata evidence**: Contextual information from payload

Generates explanation format:
```
Similarity Score: 0.87 (very similar)
```
### 6.1 Automatic Success Path (Local)
1. User selects two similar documents in search results or visualization
2. Clicks "Explain Similarity" button
3. Text Artifact Resolver extracts both documents
4. Local LLM (Ollama) generates explanation in 2-5 seconds
5. UI shows explanation with model attribution
6. User can copy, export, or request regeneration

### 6.2 Fallback Path
1. Text extraction fails for one or both documents
2. UI shows: "Document text not found. Paste below to enable explanation:"
3. User pastes missing text
4. Explanation proceeds normally

### 6.3 Cloud Provider Path (Optional)
1. User opens Preferences → Similarity Explanations
2. Selects "Use Cloud Provider" + chooses OpenAI/Anthropic/Google
3. Enters API key (stored encrypted locally)
4. Future explanations show cost estimate: "~$0.002 per comparison"
5. User confirms, gets higher-quality cloud explanation

### 6.1 Automatic Success Path
1. User selects datapoint
2. Source Resolver identifies artifact
3. Artifact is retrieved
4. Inspector displays preview
5. Similarity explanation uses correct model

### 6.2 Fallback Path
1. Source Resolver fails or retrieval fails
2. Inspector displays metadata
3.**Missing text**: Show metadata, allow manual paste
- **Very long documents**: Truncate to model context limit (4k-128k tokens)
- **Non-English text**: Local models handle reasonably well
- **Private/authenticated URLs**: Don't auto-fetch without user confirmation
- **Ollama not installed**: Show setup instructions, fall back to manual explanation
- **API key invalid**: Clear error message, offer to re-enter
- **Rate limits exceeded**: Show backoff message, suggest local model

System must fail gracefully with actionable error messages
- Incorrect file extensions
- Private or authenticated URLs
- Text extraction: < 100ms for most cases
- Local LLM explanation: 2-10 seconds (depends on model size and hardware)
- Cloud LLM explanation: 1-5 seconds (depends on provider)
- Show progress indicator for explanations > 1 second
- Non-blocking UI: use background threads for all LLM calls
- Cache explanations: same document pair = instant repeat viewarly.

## 8. Performance Requirements
- Source Resolver must complete inference in < 50ms.
- Artifact retrieval must timeout gracefully.
- Similarity explanations must complete within model provider limits.
- No blocking UI during resolution.
**Local-first = Privacy-first**: Documents never leave machine with local models
- Cloud providers: Warn user before sending text to external APIs
- API keys: Store encrypted in system keyring (not plaintext config)
- No telemetry: Explanation content never logged or transmitted
## 10. Implementation Phases

### Phase 2A: Text-Only + Local Models (MVP)
**Timeline: 1-2 weeks**
- Text artifact resolver
- Ollama integration
- Basic similarity explanation UI
- Manual text input fallback
- Ships as free feature

### Phase 2B: Cloud Provider Support (Optional)
**Timeline: 3-5 days**
- OpenAI, Anthropic, Google integrations
- API key management
- Cost estimation
- Ships as Pro feature

### Phase 3: Enhancements
**Timeline: Future**
- Explanation quality scoring
- Multi-document comparison (compare 3+ at once)
- Explanation export/sharing
- Custom prompt templates

### Phase 4: Multimodal (Future)
**Timeline: TBD based on demand**
- Image similarity (vision models)
- Audio similarity
- Mixed-modality collections

See Section 12 for detailed multimodal architecture.

## 11. Success Metrics
- **Adoption**: % of users who try similarity explanations
- **Satisfaction**: User feedback on explanation quality
- **Performance**: Average explanation latency < 5 seconds
- **Cost**: Cloud API costs (for Pro users) < $0.01 per comparison
- **Privacy**: 0% of users report data concerns with local models

---

## 12. Future: Multimodal Support Architecture

**Note**: This section describes future functionality beyond Phase 1 text-only support. Implementation timeline depends on user demand and technical validation.

### 12.1 Modality Detection System

When multimodal support is added, the system will need to automatically determine artifact types. This will be handled by a **Multimodal Artifact Resolver** that extends the current text-only resolver.

#### Inference Layers (Priority Order)

1. **Explicit Metadata**
   - Check for: `type`, `mime_type`, `content_type`, `media_type`
   - Example: `{"type": "image", "mime_type": "image/jpeg"}`
   - Confidence: 0.95-1.0

2. **File Extension Analysis**
   - Images: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.bmp`, `.svg`
   - Audio: `.mp3`, `.wav`, `.flac`, `.ogg`, `.m4a`, `.aac`
   - Video: `.mp4`, `.mov`, `.avi`, `.webm`, `.mkv`
   - Documents: `.pdf`, `.docx`, `.txt`, `.md`, `.html`
   - Confidence: 0.85-0.90

3. **URL Pattern Recognition**
   - Image hosts: `imgur.com`, `i.redd.it`, `*.cloudinary.com`
   - Video hosts: `youtube.com`, `vimeo.com`, `*.mp4`
   - Audio hosts: `soundcloud.com`, `*.mp3`, `*.wav`
   - Confidence: 0.75-0.85

4. **Payload Structure Heuristics**
   - Text: Presence of `text`, `document`, `content` fields
   - Image: Presence of `image_url`, `width`, `height`, `dimensions`
   - Audio: Presence of `duration`, `sample_rate`, `audio_url`
   - Video: Presence of `duration`, `fps`, `resolution`, `video_url`
   - Confidence: 0.60-0.75

5. **Content Signature (Magic Bytes)**
   - If artifact is fetched, inspect first bytes:
     - JPEG: `FF D8 FF`
     - PNG: `89 50 4E 47`
     - GIF: `47 49 46 38`
     - MP3: `FF FB` or `ID3`
     - WAV: `52 49 46 46`
     - PDF: `25 50 44 46`
   - Confidence: 1.0 (definitive if fetched)

#### Resolver Output Schema

```json
{
  "modality": "image",           // text | image | audio | video | document
  "source_type": "url",          // inline | url | file_path | unknown
  "source": "https://...",       // Location or content
  "mime_type": "image/jpeg",     // Standard MIME type
  "confidence": 0.93,            // 0.0 - 1.0
  "metadata": {
    "width": 1920,
    "height": 1080,
    "format": "JPEG"
  }
}
```

### 12.2 Artifact Retrieval Strategy

Based on resolver output:

**For `source_type = "inline"`**
```python
# Content already in metadata
return metadata["text"] or metadata["content"]
```

**For `source_type = "url"`**
```python
# Fetch with safety checks
if not is_trusted_domain(url):
    confirm = prompt_user(f"Fetch from {domain}?")
    if not confirm:
        return fallback_to_manual()

response = requests.get(url, timeout=10, max_size=10MB)
return response.content
```

**For `source_type = "file_path"`**
```python
# Local file read
if not os.path.exists(path):
    return fallback_to_manual()

# Security: only read from expected directories
if not is_safe_path(path):
    return fallback_to_manual()

return read_file(path)
```

**For `source_type = "unknown"`**
```python
# Immediate fallback to manual
return prompt_user_upload()
```

### 12.3 Model Provider Routing

Once modality is determined, route to appropriate model:

#### Text Models (Current Phase)
- **Local**: Ollama (llama3.2, mistral, qwen)
- **Cloud**: OpenAI GPT-4, Anthropic Claude, Google Gemini

#### Vision Models (Future)
- **Local**: 
  - LLaVA (7B-13B) via Ollama
  - BakLLaVA (vision-tuned Mistral)
  - CogVLM (open-source, powerful)
- **Cloud**:
  - OpenAI GPT-4 Vision
  - Anthropic Claude 3 Opus/Sonnet (vision)
  - Google Gemini Pro Vision

#### Audio Models (Future)
- **Local**:
  - Whisper (transcription) + text LLM for analysis
  - AudioCraft for audio understanding
- **Cloud**:
  - OpenAI Whisper API + GPT-4 analysis
  - Google Speech-to-Text + Gemini

#### Video Models (Future, Experimental)
- **Approach**: Frame extraction + vision model
- **Local**: Extract keyframes → LLaVA analysis
- **Cloud**: GPT-4 Vision on keyframes or direct video API

### 12.4 Multimodal Explanation Examples

#### Image Similarity Explanation
```
Similarity Score: 0.82 (similar)

Visual Similarities:
- Both images feature urban architecture
- Similar color palette (blues and grays)
- Both taken during daytime with clear skies
- Comparable composition: buildings in foreground, sky in background

Key Differences:
- Image A shows modern glass skyscrapers
- Image B depicts historic brick buildings
- Different architectural styles: contemporary vs. Victorian

Detected Objects:
- Image A: buildings, windows, clouds, street
- Image B: buildings, windows, trees, pedestrians

[Powered by: llava:13b (local) | Processing time: 8.3s]
```

#### Audio Similarity Explanation
```
Similarity Score: 0.91 (very similar)

Audio Characteristics:
- Both are speech recordings (English)
- Similar speakers: male, mid-range pitch
- Comparable recording quality: studio-grade
- Similar duration: ~45 seconds each

Content Analysis:
- Audio A: Tutorial on Python programming
- Audio B: Explanation of software design patterns
- Both educational/instructional in tone
- Similar pacing and speaking style

Technical Details:
- Sample rate: 44.1kHz (both)
- Predominant frequencies: 120-280 Hz
- Low background noise in both

[Powered by: whisper-large + llama3.2:7b (local) | Processing time: 12.1s]
```

### 12.5 Mixed-Modality Collections

Some collections may contain multiple modalities. The system will handle this by:

1. **Per-Item Detection**: Determine modality for each item individually
2. **Modality Filtering**: Allow users to filter by modality type
3. **Comparison Rules**:
   - Same modality: Use specialized model (vision-to-vision)
   - Different modalities: Fall back to metadata comparison or refuse
4. **UI Indicators**: Clear icons showing item modality (📄 text, 🖼️ image, 🎵 audio)

### 12.6 Edge Cases & Challenges

**Challenge 1: Large Media Files**
- Images: Resize to max 2048px before sending to model
- Audio: Truncate to first 30 seconds or summarize
- Video: Extract 5-10 keyframes instead of full video

**Challenge 2: Proprietary Formats**
- Convert to standard formats (e.g., HEIC → JPEG)
- Use `ffmpeg` for audio/video conversion
- Fall back to metadata if conversion fails

**Challenge 3: Access Control**
- Private URLs requiring auth
- Local files with restricted permissions
- Cloud storage with temporary signed URLs

**Solution**: Always provide manual upload option as safety net.

**Challenge 4: Cost Management (Cloud Models)**
- Vision models cost 5-10x more than text models
- Show clear cost estimate before processing
- Option to use lower-cost local models
- Batch processing discounts when available

### 12.7 Implementation Priority

When multimodal support is added, prioritize in this order:

1. **Images** (highest demand, well-supported models)
   - Timeline: 2-3 weeks after text is stable
   - Start with local LLaVA via Ollama
   - Add cloud vision APIs for Pro tier

2. **Audio** (medium demand, transcription-first approach)
   - Timeline: 1-2 weeks after images
   - Use Whisper (local) for transcription
   - Reuse text LLM infrastructure for analysis

3. **Video** (lower priority, experimental)
   - Timeline: TBD based on user requests
   - Frame extraction approach first
   - Consider future native video models

4. **Documents** (PDFs, DOCX)
   - Timeline: Medium priority
   - Extract text first (existing tools)
   - May add layout/formatting analysis later

---

**Recommendation**: Validate demand for each modality before building. Text covers 85-95% of use cases. Images add another 10-15%. Audio/video are niche but valuable for specific users.
- Video modality
- Document modality (PDF, DOCX)
- Batch artifact resolution
- Provenance tracing
- “Reconstruct missing artifacts” workflow
