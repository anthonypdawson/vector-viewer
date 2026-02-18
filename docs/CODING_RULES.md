# Coding Rule: Class-Level Type Annotations

## Rule
All classes must declare class-level type annotations for all instance attributes that are set in `__init__` or elsewhere. This ensures static analysis tools (like Pylance, mypy, etc.) can detect attribute existence and types, reducing runtime errors and improving code completion.

## Rationale
- Prevents Pylance and mypy errors about unknown attributes
- Improves code readability and maintainability
- Enables better IDE support and static analysis

## Example
```python
class MyWidget(QWidget):
    label: QLabel
    value: int
    # ...
    def __init__(self):
        super().__init__()
        self.label = QLabel()
        self.value = 0
```

## Enforcement
- All new code must follow this rule
- Updating existing classes to add class-level type annotations should be done incrementally, prioritizing frequently modified or critical classes first
- Code reviews should check for class-level type annotations
- Static analysis (mypy, Pylance) should be run in CI

---

# Copilot/AI Instructions Update

**Always add class-level type annotations for all attributes in every class you generate.**
- If a class sets attributes in `__init__`, declare them at the class level with type hints.
- This applies to all Python code, especially for PyQt/PySide, dataclasses, and any class with dynamic attributes.

## Example Instruction
> When generating Python classes, always include class-level type annotations for all attributes, even if they are set in `__init__` or other methods.

## Exception handling
> When raising exceptions in generated code, use the `from` keyword to chain exceptions for better debugging. For example, instead of:
```python
        except ImportError:
            raise ImportError("PyTorch required for CLIP. Install with: pip install torch")
```
Use:
```python
        except ImportError as ie:
            raise ImportError("PyTorch required for CLIP. Install with: pip install torch") from ie
```
---

This rule must be followed for all future code contributions and AI-generated code.
