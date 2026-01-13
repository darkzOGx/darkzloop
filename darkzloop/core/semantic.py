"""
darkzloop Semantic Expansion

Solves the "Vocabulary Gap" problem where developers use different terms
for the same concept (User says "Login", Codebase says "Auth").

Features:
1. Semantic Expansion - Expands keywords to synonym clusters
2. Codebase Learning - Learns terminology from actual file names
3. Glossary Persistence - Remembers associations across runs

This runs as a Pre-Flight step during `darkzloop plan`.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path
import json
import re
from datetime import datetime


# =============================================================================
# Built-in Synonym Clusters (Domain Knowledge)
# =============================================================================

BUILTIN_SYNONYMS: Dict[str, List[str]] = {
    # Authentication
    "login": ["auth", "signin", "authenticate", "session", "credential"],
    "logout": ["signout", "deauth", "session_destroy"],
    "auth": ["authentication", "login", "identity", "oauth", "jwt", "token"],
    "user": ["account", "profile", "member", "identity", "principal"],
    "password": ["credential", "secret", "passphrase", "pwd"],
    "permission": ["role", "access", "privilege", "acl", "rbac", "authorization"],
    
    # E-commerce
    "cart": ["basket", "bag", "shopping_cart"],
    "checkout": ["purchase", "order", "payment", "buy"],
    "billing": ["invoice", "payment", "subscription", "charge", "stripe", "pricing"],
    "payment": ["billing", "charge", "transaction", "stripe", "paypal"],
    "product": ["item", "sku", "merchandise", "goods", "inventory"],
    "order": ["purchase", "transaction", "checkout", "booking"],
    "customer": ["client", "buyer", "user", "account"],
    
    # Data
    "database": ["db", "store", "persistence", "repository", "storage"],
    "query": ["search", "find", "fetch", "select", "lookup"],
    "cache": ["memo", "store", "redis", "memcache"],
    "model": ["entity", "schema", "record", "domain"],
    "migration": ["schema", "alter", "upgrade", "evolve"],
    
    # API
    "endpoint": ["route", "handler", "controller", "api"],
    "request": ["req", "input", "payload"],
    "response": ["res", "output", "reply"],
    "middleware": ["interceptor", "filter", "guard", "pipe"],
    "validation": ["verify", "check", "guard", "assert", "sanitize"],
    
    # Events
    "event": ["message", "signal", "notification", "webhook", "trigger"],
    "publish": ["emit", "send", "dispatch", "broadcast"],
    "subscribe": ["listen", "consume", "handle", "observe"],
    "queue": ["job", "task", "worker", "background"],
    
    # UI
    "component": ["widget", "element", "view", "partial"],
    "page": ["screen", "view", "route", "template"],
    "modal": ["dialog", "popup", "overlay"],
    "form": ["input", "field", "control"],
    "button": ["btn", "action", "trigger"],
    
    # Common Actions
    "create": ["add", "new", "insert", "make", "generate"],
    "update": ["edit", "modify", "patch", "change"],
    "delete": ["remove", "destroy", "drop", "purge"],
    "list": ["index", "all", "fetch", "get_all", "find_all"],
    "get": ["fetch", "find", "read", "retrieve", "load"],
    
    # Testing
    "test": ["spec", "check", "verify", "assert"],
    "mock": ["stub", "fake", "spy", "double"],
    "fixture": ["factory", "seed", "sample"],
    
    # Config
    "config": ["settings", "options", "preferences", "env"],
    "environment": ["env", "config", "context"],
}


@dataclass
class SemanticMatch:
    """A matched file/path with semantic relevance."""
    path: str
    matched_term: str  # The synonym that matched
    original_term: str  # The user's original term
    confidence: float  # 0.0-1.0, direct match = 1.0, synonym = 0.8


@dataclass
class Glossary:
    """
    Project-specific glossary that learns terminology.
    
    Persisted to .darkzloop/glossary.json
    """
    # Learned associations: user_term -> [codebase_terms]
    learned: Dict[str, Set[str]] = field(default_factory=dict)
    
    # Frequency counts for ranking
    term_frequencies: Dict[str, int] = field(default_factory=dict)
    
    # Last updated
    updated_at: Optional[str] = None
    
    def add_association(self, user_term: str, codebase_term: str):
        """Learn that user_term maps to codebase_term."""
        user_term = user_term.lower()
        codebase_term = codebase_term.lower()
        
        if user_term not in self.learned:
            self.learned[user_term] = set()
        
        self.learned[user_term].add(codebase_term)
        
        # Track frequency
        self.term_frequencies[codebase_term] = self.term_frequencies.get(codebase_term, 0) + 1
        self.updated_at = datetime.now().isoformat()
    
    def get_associations(self, term: str) -> List[str]:
        """Get learned associations for a term."""
        return list(self.learned.get(term.lower(), set()))
    
    def to_dict(self) -> dict:
        return {
            "learned": {k: list(v) for k, v in self.learned.items()},
            "term_frequencies": self.term_frequencies,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Glossary":
        glossary = cls()
        glossary.learned = {k: set(v) for k, v in data.get("learned", {}).items()}
        glossary.term_frequencies = data.get("term_frequencies", {})
        glossary.updated_at = data.get("updated_at")
        return glossary


class SemanticExpander:
    """
    Expands search terms to synonym clusters.
    
    Combines:
    1. Built-in domain knowledge
    2. Project-specific glossary (learned)
    3. Codebase analysis (on-the-fly)
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.glossary_path = project_root / ".darkzloop" / "glossary.json"
        self.glossary = self._load_glossary()
        
        # Cache of codebase terms (file/folder names)
        self._codebase_terms: Optional[Set[str]] = None
    
    def _load_glossary(self) -> Glossary:
        """Load or create glossary."""
        if self.glossary_path.exists():
            try:
                with open(self.glossary_path) as f:
                    return Glossary.from_dict(json.load(f))
            except (json.JSONDecodeError, KeyError):
                pass
        return Glossary()
    
    def save_glossary(self):
        """Persist glossary to disk."""
        self.glossary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.glossary_path, 'w') as f:
            json.dump(self.glossary.to_dict(), f, indent=2)
    
    def _scan_codebase_terms(self) -> Set[str]:
        """Extract terms from file and folder names."""
        terms = set()
        
        # Common source directories
        src_dirs = ["src", "lib", "app", "pkg", "internal", "cmd"]
        
        for src in src_dirs:
            src_path = self.project_root / src
            if src_path.exists():
                for path in src_path.rglob("*"):
                    if path.is_file() or path.is_dir():
                        # Extract meaningful terms from path
                        name = path.stem.lower()
                        # Split on common separators
                        parts = re.split(r'[_\-./]', name)
                        terms.update(p for p in parts if len(p) > 2)
        
        return terms
    
    @property
    def codebase_terms(self) -> Set[str]:
        """Lazy-load codebase terms."""
        if self._codebase_terms is None:
            self._codebase_terms = self._scan_codebase_terms()
        return self._codebase_terms
    
    def expand(self, term: str, include_codebase: bool = True) -> Dict[str, float]:
        """
        Expand a term to synonym cluster with confidence scores.
        
        Returns: {synonym: confidence_score}
        """
        term = term.lower()
        results: Dict[str, float] = {term: 1.0}  # Original term has full confidence
        
        # 1. Built-in synonyms
        if term in BUILTIN_SYNONYMS:
            for syn in BUILTIN_SYNONYMS[term]:
                results[syn] = max(results.get(syn, 0), 0.9)
        
        # Also check if term is a synonym of something else
        for key, synonyms in BUILTIN_SYNONYMS.items():
            if term in synonyms:
                results[key] = max(results.get(key, 0), 0.9)
                for syn in synonyms:
                    results[syn] = max(results.get(syn, 0), 0.85)
        
        # 2. Learned glossary (project-specific, highest value)
        for learned in self.glossary.get_associations(term):
            # Learned associations are high confidence
            freq = self.glossary.term_frequencies.get(learned, 1)
            confidence = min(0.95, 0.85 + (freq * 0.02))  # More frequent = higher confidence
            results[learned] = max(results.get(learned, 0), confidence)
        
        # 3. Codebase terms (fuzzy match)
        if include_codebase:
            for codebase_term in self.codebase_terms:
                # Check for substring match
                if term in codebase_term or codebase_term in term:
                    results[codebase_term] = max(results.get(codebase_term, 0), 0.7)
                # Check for prefix match
                elif codebase_term.startswith(term) or term.startswith(codebase_term):
                    results[codebase_term] = max(results.get(codebase_term, 0), 0.6)
        
        return results
    
    def expand_multiple(self, terms: List[str]) -> Dict[str, Dict[str, float]]:
        """Expand multiple terms."""
        return {term: self.expand(term) for term in terms}
    
    def generate_search_strategy(self, terms: List[str], top_n: int = 5) -> List[str]:
        """
        Generate shell commands for searching.
        
        Returns grep/ripgrep commands covering synonym clusters.
        """
        all_search_terms = set()
        
        for term in terms:
            expansion = self.expand(term)
            # Take top N by confidence
            sorted_terms = sorted(expansion.items(), key=lambda x: -x[1])[:top_n]
            all_search_terms.update(t for t, _ in sorted_terms)
        
        # Generate search commands
        commands = []
        for search_term in sorted(all_search_terms):
            # Prefer ripgrep if available, fallback to grep
            commands.append(f"rg -i '{search_term}' src/ || grep -ri '{search_term}' src/")
        
        return commands
    
    def search_files(self, terms: List[str], extensions: List[str] = None) -> List[SemanticMatch]:
        """
        Search for files matching term clusters.
        
        Returns matches with semantic relevance.
        """
        if extensions is None:
            extensions = [".rs", ".py", ".ts", ".js", ".go", ".java", ".rb"]
        
        matches: List[SemanticMatch] = []
        seen_paths = set()
        
        for term in terms:
            expansion = self.expand(term)
            
            for search_term, confidence in expansion.items():
                # Search file names
                for ext in extensions:
                    pattern = f"**/*{search_term}*{ext}"
                    for path in self.project_root.glob(pattern):
                        if path.is_file() and str(path) not in seen_paths:
                            seen_paths.add(str(path))
                            matches.append(SemanticMatch(
                                path=str(path.relative_to(self.project_root)),
                                matched_term=search_term,
                                original_term=term,
                                confidence=confidence,
                            ))
                
                # Search folder names
                pattern = f"**/*{search_term}*/"
                for path in self.project_root.glob(pattern):
                    if path.is_dir() and str(path) not in seen_paths:
                        # Find files in this directory
                        for file in path.iterdir():
                            if file.is_file() and file.suffix in extensions:
                                file_path = str(file.relative_to(self.project_root))
                                if file_path not in seen_paths:
                                    seen_paths.add(file_path)
                                    matches.append(SemanticMatch(
                                        path=file_path,
                                        matched_term=search_term,
                                        original_term=term,
                                        confidence=confidence * 0.9,  # Slightly lower for folder match
                                    ))
        
        # Sort by confidence
        matches.sort(key=lambda m: -m.confidence)
        return matches
    
    def learn_from_success(self, user_term: str, matched_file: str):
        """
        Learn association when a search succeeds.
        
        Called when agent finds relevant code.
        """
        # Extract terms from the file path
        path = Path(matched_file)
        file_terms = re.split(r'[_\-./]', path.stem.lower())
        
        for term in file_terms:
            if len(term) > 2 and term != user_term.lower():
                self.glossary.add_association(user_term, term)
        
        # Save glossary
        self.save_glossary()
    
    def extract_spec_terms(self, spec_content: str) -> List[str]:
        """
        Extract key domain terms from a spec.
        
        Identifies nouns that are likely to be domain concepts.
        """
        # Common patterns that indicate domain terms
        patterns = [
            r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)*)\b',  # PascalCase
            r'\b([a-z]+_[a-z]+)\b',                 # snake_case
            r'`([a-z_]+)`',                         # backtick code
            r'"([A-Za-z]+)"',                       # quoted terms
        ]
        
        terms = set()
        for pattern in patterns:
            matches = re.findall(pattern, spec_content)
            for match in matches:
                term = match.lower().replace('_', ' ').strip()
                if len(term) > 2:
                    terms.add(term.replace(' ', '_'))
        
        # Also extract from headers
        header_pattern = r'^#+\s+(.+)$'
        for match in re.findall(header_pattern, spec_content, re.MULTILINE):
            words = match.lower().split()
            terms.update(w for w in words if len(w) > 3)
        
        return list(terms)
    
    def to_prompt_fragment(self, terms: List[str]) -> str:
        """
        Generate a prompt fragment explaining the semantic expansion.
        
        Injected into agent context.
        """
        lines = ["## SEMANTIC EXPANSION", ""]
        lines.append("The following terms have been expanded to include synonyms:")
        lines.append("")
        
        for term in terms[:10]:  # Limit to prevent token bloat
            expansion = self.expand(term)
            top_5 = sorted(expansion.items(), key=lambda x: -x[1])[:5]
            synonyms = [f"{t} ({c:.0%})" for t, c in top_5 if t != term]
            if synonyms:
                lines.append(f"- **{term}**: {', '.join(synonyms)}")
        
        lines.append("")
        lines.append("When searching for code, use these synonym clusters.")
        
        return "\n".join(lines)


# =============================================================================
# LLM-Powered Expansion (Optional)
# =============================================================================

def generate_synonyms_prompt(terms: List[str], context: str = "") -> str:
    """
    Generate a prompt for LLM to expand terms.
    
    Use this when built-in synonyms aren't enough.
    """
    return f"""You are analyzing a software project. Given the following domain terms, 
generate technical synonyms that might appear in a codebase.

For each term, provide 3-5 synonyms commonly used in programming.

Terms: {', '.join(terms)}

{f"Context: {context}" if context else ""}

Respond in JSON format:
{{
  "term1": ["synonym1", "synonym2", "synonym3"],
  "term2": ["synonym1", "synonym2"]
}}

Focus on:
- Common abbreviations (authentication -> auth)
- Alternative naming conventions (shopping_cart -> basket)
- Framework-specific terms (model -> entity)
- Related concepts (payment -> billing, invoice)
"""


def parse_llm_synonyms(response: str) -> Dict[str, List[str]]:
    """Parse LLM synonym response."""
    try:
        # Extract JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            return json.loads(json_match.group())
    except (json.JSONDecodeError, AttributeError):
        pass
    return {}


# =============================================================================
# Convenience Functions
# =============================================================================

def create_expander(project_path: Path) -> SemanticExpander:
    """Create an expander for a project."""
    return SemanticExpander(project_path)


def quick_expand(term: str) -> List[str]:
    """Quick expansion using only built-in synonyms."""
    results = [term]
    
    if term.lower() in BUILTIN_SYNONYMS:
        results.extend(BUILTIN_SYNONYMS[term.lower()])
    
    for key, synonyms in BUILTIN_SYNONYMS.items():
        if term.lower() in synonyms:
            results.append(key)
            results.extend(s for s in synonyms if s != term.lower())
    
    return list(set(results))


if __name__ == "__main__":
    # Demo
    print("Semantic Expander Demo")
    print("=" * 40)
    
    # Test built-in synonyms
    print("\n1. Built-in synonym expansion:")
    for term in ["billing", "login", "cart"]:
        expanded = quick_expand(term)
        print(f"   {term} -> {expanded}")
    
    # Test with project
    print("\n2. Project-aware expansion:")
    expander = SemanticExpander(Path("."))
    
    expansion = expander.expand("billing")
    print(f"   billing -> {dict(list(expansion.items())[:5])}")
    
    # Test search strategy
    print("\n3. Search strategy generation:")
    strategy = expander.generate_search_strategy(["billing", "user"])
    for cmd in strategy[:5]:
        print(f"   {cmd}")
    
    # Test prompt fragment
    print("\n4. Agent prompt fragment:")
    fragment = expander.to_prompt_fragment(["billing", "auth"])
    print(fragment)
