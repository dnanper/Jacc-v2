from enum import StrEnum


class NodeLabel(StrEnum):
    """All node labels in the knowledge graph."""

    PROJECT = "Project"
    PACKAGE = "Package"
    MODULE = "Module"
    FOLDER = "Folder"
    FILE = "File"

    CLASS = "Class"
    FUNCTION = "Function"
    METHOD = "Method"
    VARIABLE = "Variable"
    INTERFACE = "Interface"
    ENUM = "Enum"
    DECORATOR = "Decorator"
    IMPORT = "Import"
    TYPE = "Type"
    CODE_ELEMENT = "CodeElement"

    COMMUNITY = "Community"
    PROCESS = "Process"

    STRUCT = "Struct"
    MACRO = "Macro"
    TYPEDEF = "Typedef"
    UNION = "Union"
    NAMESPACE = "Namespace"
    TRAIT = "Trait"
    IMPL = "Impl"
    TYPE_ALIAS = "TypeAlias"
    CONST = "Const"
    STATIC = "Static"
    PROPERTY = "Property"
    RECORD = "Record"
    DELEGATE = "Delegate"
    ANNOTATION = "Annotation"
    CONSTRUCTOR = "Constructor"
    TEMPLATE = "Template"

    SECTION = "Section"
