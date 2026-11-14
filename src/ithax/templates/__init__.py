"""Template packages (spec 4 "Template package"; AKS-122).

``load_package`` reads and checks one ``templates/<template_id>/`` folder; ``lesson``
parses ``lesson.md``; ``expected`` reads ``expected.json`` and judges a run's
``summary.json`` against it.
"""

from ithax.templates.expected import ExpectedRow, judge, summary_estimates
from ithax.templates.lesson import Lesson, parse_lesson
from ithax.templates.package import (
    TEMPLATE_ISSUE,
    PackageResult,
    TemplatePackage,
    load_package,
    package_folders,
)

__all__ = [
    "TEMPLATE_ISSUE",
    "ExpectedRow",
    "Lesson",
    "PackageResult",
    "TemplatePackage",
    "judge",
    "load_package",
    "package_folders",
    "parse_lesson",
    "summary_estimates",
]
