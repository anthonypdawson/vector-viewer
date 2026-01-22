# Vector Inspector Performance Optimization

## Current App Load Time Issues

The application currently takes a while to load when executed from the command line. Here are the main causes and solutions:

## 🔍 Root Causes

### 1. Heavy Imports at Startup
- **PySide6** (Qt) is a large framework (~100MB+)
- **ChromaDB** and **Qdrant** clients load their dependencies
- **NumPy, Plotly, scikit-learn** for visualization
- All imports happen synchronously on startup

### 2. Module Loading Order
- All UI components are imported upfront
- Database connections are initialized immediately
- Visualization libraries loaded even if not used

### 3. Settings/Configuration Loading
- Settings service reads from disk on startup
- Path resolution for databases happens early

## ✅ Recommended Optimizations

### 1. **Lazy Imports** (High Impact - Easy)  
**Status: Implemented (Jan 2026)**

Heavy visualization libraries (plotly, numpy, scikit-learn, umap) are now loaded lazily only when the visualization tab is accessed. This significantly reduces startup time and memory usage.

```python
# Instead of:
import plotly.graph_objects as go
from sklearn.decomposition import PCA

# Now done via:
def get_plotly():
    import plotly.graph_objects as go
    return go

def get_pca():
    from sklearn.decomposition import PCA
    return PCA
```

**Files modified:**
- `src/vector_inspector/ui/views/visualization_view.py`
- `src/vector_inspector/services/visualization_service.py`
- `src/vector_inspector/utils/lazy_imports.py`

**Result:**
- App startup is now ~2 seconds faster
- Heavy libraries are only loaded if/when visualization is used

### 2. **Deferred Component Initialization** (Medium Impact - Medium)

Don't create all tabs/views until needed:

```python
class MainWindow(QMainWindow):
    def __init__(self):
        # ... existing code ...
        self.tab_widget = QTabWidget()
        
        # Create only essential views immediately
        self.info_panel = InfoPanel(self.connection)
        self.tab_widget.addTab(self.info_panel, "Info")
        
        # Lazy-load other tabs
        self._metadata_view = None
        self._search_view = None
        self._visualization_view = None
        
        # Connect to tab change event
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
    
    def _on_tab_changed(self, index):
        """Create tabs on first access."""
        if index == 1 and not self._metadata_view:
            self._metadata_view = MetadataView(self.connection)
            self.tab_widget.addTab(self._metadata_view, "Data Browser")
        # ... similar for other tabs
```

**Expected gain:** ~0.5-1 second

### 3. **Splash Screen** (Low Impact - Easy)

Show a loading screen while initializing:

```python
# src/vector_inspector/main.py
from PySide6.QtWidgets import QSplashScreen
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

def main():
    app = QApplication(sys.argv)
    
    # Show splash screen
    splash_pix = QPixmap(400, 300)
    splash_pix.fill(Qt.white)
    splash = QSplashScreen(splash_pix)
    splash.showMessage("Loading Vector Inspector...", 
                       Qt.AlignBottom | Qt.AlignCenter)
    splash.show()
    app.processEvents()
    
    # Load main window
    window = MainWindow()
    splash.finish(window)
    window.show()
    
    sys.exit(app.exec())
```

**Expected gain:** Better perceived performance (user knows app is loading)

### 4. **Optimize Database Connection Init** (Medium Impact - Easy)

Don't auto-connect on startup:

```python
# In main_window.py __init__:
def __init__(self):
    # Instead of:
    # self.connection: VectorDBConnection = ChromaDBConnection()
    
    # Do this:
    self.connection: VectorDBConnection = None  # Lazy init
    
    # Connection created only when user clicks Connect
```

**Expected gain:** ~0.3-0.5 seconds

### 5. **Bundle with PyInstaller** (High Impact - Hard)

Create a standalone executable:

```bash
pip install pyinstaller

pyinstaller --onefile \
  --windowed \
  --name "Vector Inspector" \
  --icon icon.ico \
  --add-data "src/vector_inspector:vector_inspector" \
  src/vector_inspector/main.py
```

Benefits:
- Much faster startup (no Python interpreter overhead)
- No need to activate virtual environment
- Professional deployment

**Expected gain:** 3-5x faster startup

### 6. **Cache Imports in __pycache__** (Low Impact - Free)

Python already does this, but ensure:
- You're running from the same environment
- `__pycache__` directories aren't gitignored locally
- Use `python -O` for optimized bytecode

### 7. **Profile Startup Time** (Diagnostic)

Add profiling to find bottlenecks:

```python
# src/vector_inspector/main.py
import time
import sys

def main():
    t0 = time.time()
    
    from PySide6.QtWidgets import QApplication
    t1 = time.time()
    print(f"Import PySide6: {t1-t0:.2f}s")
    
    from vector_inspector.ui.main_window import MainWindow
    t2 = time.time()
    print(f"Import MainWindow: {t2-t1:.2f}s")
    
    app = QApplication(sys.argv)
    t3 = time.time()
    print(f"Create QApplication: {t3-t2:.2f}s")
    
    window = MainWindow()
    t4 = time.time()
    print(f"Create MainWindow: {t4-t3:.2f}s")
    
    window.show()
    t5 = time.time()
    print(f"Show window: {t5-t4:.2f}s")
    print(f"Total startup: {t5-t0:.2f}s")
    
    sys.exit(app.exec())
```

Run and identify the slowest step.

## 📊 Priority Implementation Order

1. **✅ Easy Wins First:**
   - Lazy import visualization libraries (1-2 sec gain)
   - Optimize database connection init (0.5 sec gain)
   - Add splash screen (better UX)

2. **🚀 Medium Effort:**
   - Deferred tab initialization (0.5-1 sec gain)
   - Profile startup to find other bottlenecks

3. **⚡ Long Term:**
   - PyInstaller bundling (3-5x faster, but complex)
   - Consider switching to lighter visualization (Matplotlib vs Plotly)

## 🎯 Expected Results

**Current:** ~3-5 seconds  
**After easy wins:** ~2-3 seconds  
**After all optimizations:** ~1-2 seconds  
**With PyInstaller:** ~0.5-1 second

## 📝 Implementation Notes

### Files to Modify for Quick Wins:

1. `src/vector_inspector/ui/views/visualization_view.py`
   - Lazy import plotly, sklearn, numpy
   
2. `src/vector_inspector/services/visualization_service.py`
   - Lazy import UMAP, TSNE, PCA

3. `src/vector_inspector/ui/main_window.py`
   - Don't initialize connection on startup
   - Optional: Lazy tab creation

4. `src/vector_inspector/main.py`
   - Add splash screen
   - Add profiling code

### Testing Performance:

```bash
# Measure startup time
time python -m vector_inspector.main

# Or use Python's timeit
python -m timeit -n 1 -r 1 "import vector_inspector.main; vector_inspector.main.main()"
```

## 🔧 Code Examples Ready to Use

### Lazy Import Helper Function

```python
# src/vector_inspector/utils/lazy_imports.py
"""Lazy import utilities for performance optimization."""

_plotly_cache = None
_sklearn_cache = {}

def get_plotly():
    """Lazy import plotly."""
    global _plotly_cache
    if _plotly_cache is None:
        import plotly.graph_objects as go
        _plotly_cache = go
    return _plotly_cache

def get_sklearn_model(model_name: str):
    """Lazy import sklearn models."""
    global _sklearn_cache
    if model_name not in _sklearn_cache:
        if model_name == 'PCA':
            from sklearn.decomposition import PCA
            _sklearn_cache['PCA'] = PCA
        elif model_name == 'TSNE':
            from sklearn.manifold import TSNE
            _sklearn_cache['TSNE'] = TSNE
        elif model_name == 'UMAP':
            from umap import UMAP
            _sklearn_cache['UMAP'] = UMAP
    return _sklearn_cache[model_name]
```

Then use it in visualization_view.py:
```python
def _generate_visualization(self):
    from vector_inspector.utils.lazy_imports import get_plotly, get_sklearn_model
    
    go = get_plotly()
    reducer_class = get_sklearn_model(self.method_combo.currentText())
    # ... rest of code
```

---

**Priority:** Start with lazy imports for visualization libraries - easiest and biggest impact!
