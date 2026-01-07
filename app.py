
def tip_for(ex):
    # One short, teacher-like sentence for feedback (per question)
    tip = (ex.get("error_tip") or "").strip()
    if tip:
        return tip
    return hint_for(ex)

import json
import random
from pathlib import Path

import streamlit as st
st.set_page_config(
    page_title="Askip'en STMG - Calculs",
    layout="centered",
    initial_sidebar_state="collapsed"
)

APP_TITLE = "Askip'en STMG Calculs"
DATA_PATH = Path(__file__).parent / "exercises.json"


def _sample_param(spec, rng, already):
    t = spec.get("type", "int")
    mn = spec.get("min")
    mx = spec.get("max")
    step = spec.get("step", 1)
    if t == "int":
        candidates = list(range(int(mn), int(mx) + 1, int(step)))
        return int(rng.choice(candidates))
    if t == "float":
        # Use a discretized grid to avoid floating drift
        grid = []
        v = float(mn)
        while v <= float(mx) + 1e-9:
            grid.append(round(v, 2))
            v += float(step)
        return float(rng.choice(grid))
    raise ValueError(f"Unknown param type: {t}")


def _format_placeholders(s: str, params: dict):
    try:
        return s.format(**params)
    except Exception:
        return s


def load_exercises():
    """Load base exercises and expand templates into concrete variants."""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    expanded = []
    for e in raw:
        if e.get("qtype") != "template_number":
            expanded.append(e)
            continue

        tpl = e.get("template", {})
        n_variants = int(tpl.get("n_variants", 3))
        params_spec = tpl.get("params_spec", {})
        formula = tpl.get("formula", "")
        expl_tpl = tpl.get("explanation", "")

        # Deterministic RNG per template id (stable across refresh)
        rng = random.Random(e["id"])

        for k in range(1, n_variants + 1):
            params = {}
            # sample with constraints
            for pname, pspec in params_spec.items():
                params[pname] = _sample_param(pspec, rng, params)

            # enforce simple 'lt' constraints if present
            for pname, pspec in params_spec.items():
                if "lt" in pspec:
                    other = pspec["lt"]
                    tries = 0
                    while params[pname] >= params.get(other, params[pname] + 1):
                        params[pname] = _sample_param(pspec, rng, params)
                        tries += 1
                        if tries > 50:
                            # fallback
                            params[pname] = max(params.get(other, 0) - 1, pspec.get("min", 0))
                            break

            # compute answer
            safe_locals = dict(params)
            try:
                ans = eval(formula, {"__builtins__": {}}, safe_locals)
            except Exception:
                ans = None

            # cast to int if all params int and ans is close
            if isinstance(ans, float) and abs(ans - round(ans)) < 1e-9:
                ans = int(round(ans))

            params_with_ans = dict(params)
            params_with_ans["ans"] = format_number(ans) if ans is not None else "?"

            ex_id = f"{e['id']}_v{k}"
            expanded.append(
                {
                    **{kk: vv for kk, vv in e.items() if kk not in ["template"]},
                    "id": ex_id,
                    "qtype": "number",
                    "answer": ans,
                    "title": _format_placeholders(e.get("title", ""), params),
                    "context": _format_placeholders(e.get("context", ""), params),
                    "question": _format_placeholders(e.get("question", ""), params),
                    "explanation": _format_placeholders(expl_tpl, params_with_ans),
                }
            )

    return expanded


def init_state():
    if "solved" not in st.session_state:
        st.session_state.solved = set()
    if "attempts" not in st.session_state:
        st.session_state.attempts = {}
    if "current_id" not in st.session_state:
        st.session_state.current_id = None



HINTS_BY_TAG = {
    "ci_vs_autres": "Indice : pour la VA, on prend les consommations intermédiaires (achats consommés + charges externes). On n'y met ni impôts, ni salaires.",
    "charges_vs_produits": "Indice : commence par classer (charge ou produit) puis par nature (exploitation/financier/exceptionnel).",
    "actif_passif": "Indice : ACTIF = ce que l'entreprise possède ; PASSIF = ce qu'elle doit + ses ressources (capitaux propres).",
    "brut_net_amort": "Indice : Valeur nette = Brut − Amortissements cumulés.",
    "unitaire_global": "Indice : vérifie si on te demande un résultat unitaire (par produit) ou global (pour une quantité).",
    "pourcentage": "Indice : un taux se calcule souvent (valeur / base) × 100. Attention à la base (CA, PV, etc.).",
    "cout_achat_vs_revient": "Indice : coût d’achat = ingrédients/marchandises ; coût de revient = coût d’achat + production + distribution.",
    "marge": "Indice : marge unitaire = PV − coût unitaire. Ensuite, multiplie par la quantité pour une marge totale.",
    "classement_postes": "Indice : repère le bon bloc : exploitation / financier / exceptionnel.",
}

def hint_for(ex):
    tags = ex.get("error_tags", []) or []
    for t in tags:
        if t in HINTS_BY_TAG:
            return HINTS_BY_TAG[t]
    return "Indice : relis l'énoncé et vérifie les données à inclure."
def almost_equal(a, b, tol=1e-2):
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False


def format_number(x):
    try:
        # Show integers without decimals, else 2 decimals
        xf = float(x)
        if abs(xf - int(xf)) < 1e-9:
            return str(int(xf))
        return f"{xf:.2f}".replace(".", ",")
    except Exception:
        return str(x)



def normalize_num(s: str):
    if s is None:
        return None
    cleaned = str(s).replace(" ", "").replace("\u202f", "").replace(",", ".")
    try:
        return float(cleaned)
    except Exception:
        return None


def render_question(ex, section_key: str):
    """Render and check a question depending on qtype."""
    qtype = ex.get("qtype") or ex.get("type") or "number"
    unit = ex.get("unit", "")
    ex_id = ex["id"]
    st.session_state.attempts.setdefault(ex_id, 0)

    # Solution toggle per exercise
    sol_key = f"show_solution_{ex_id}"
    if sol_key not in st.session_state:
        st.session_state[sol_key] = False

    if qtype == "number":
        answer = ex["answer"]
        tol = float(ex.get("tolerance", 0.01))
        user_val = st.text_input(
            f"Ta réponse{(' (' + unit + ')') if unit else ''}",
            key=f"input_{section_key}_{ex_id}",
            placeholder="Ex: 320000 ou 320000,50",
        )

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("✅ Vérifier", key=f"check_{section_key}_{ex_id}"):
                st.session_state.attempts[ex_id] += 1
                val = normalize_num(user_val)
                if val is None:
                    st.error("Entre un nombre (ex: 320000 ou 320000,50).")
                else:
                    if almost_equal(val, answer, tol=tol):
                        st.success("Correct ✅")
                        st.session_state.solved.add(ex_id)
                    else:
                        st.error("Incorrect ❌")
                        st.warning(tip_for(ex))

        with c2:
            if st.button("👀 Voir la correction", key=f"sol_{section_key}_{ex_id}"):
                st.session_state[sol_key] = True

        st.caption(f"Tentatives : {st.session_state.attempts[ex_id]}")
        if st.session_state[sol_key]:
            st.markdown("### Correction (méthode)")
            st.markdown(ex.get("explanation", ""))
            st.markdown(f"**Réponse attendue :** {format_number(answer)} {unit}".strip())

    elif qtype == "single_select":
        options = list(ex.get("options", []))
        # Shuffle consistently per exercise
        rng = random.Random(ex_id)
        rng.shuffle(options)
        choice = st.radio("Choisis une réponse", options, key=f"radio_{section_key}_{ex_id}")
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("✅ Vérifier", key=f"check_{section_key}_{ex_id}"):
                st.session_state.attempts[ex_id] += 1
                if choice == ex["answer"]:
                    st.success("Correct ✅")
                    st.session_state.solved.add(ex_id)
                else:
                    st.error("Incorrect ❌")
                    st.warning(tip_for(ex))
        with c2:
            if st.button("👀 Voir la correction", key=f"sol_{section_key}_{ex_id}"):
                st.session_state[sol_key] = True
        st.caption(f"Tentatives : {st.session_state.attempts[ex_id]}")
        if st.session_state[sol_key]:
            st.markdown("### Correction (méthode)")
            st.markdown(ex.get("explanation", ""))
            st.markdown(f"**Réponse attendue :** {ex['answer']}")

    elif qtype == "multi_select":
        options = list(ex.get("options", []))
        rng = random.Random(ex_id)
        rng.shuffle(options)
        picks = st.multiselect("Sélectionne toutes les bonnes réponses", options, key=f"multi_{section_key}_{ex_id}")
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("✅ Vérifier", key=f"check_{section_key}_{ex_id}"):
                st.session_state.attempts[ex_id] += 1
                expected = set(ex["answer"])
                got = set(picks)
                if got == expected:
                    st.success("Correct ✅")
                    st.session_state.solved.add(ex_id)
                else:
                    st.error("Incorrect ❌")
                    # Helpful feedback
                    missing = expected - got
                    extra = got - expected
                    if missing:
                        st.info("Il manque : " + ", ".join(sorted(missing)))
                    if extra:
                        st.info("À retirer : " + ", ".join(sorted(extra)))
                    st.warning(tip_for(ex))
        with c2:
            if st.button("👀 Voir la correction", key=f"sol_{section_key}_{ex_id}"):
                st.session_state[sol_key] = True
        st.caption(f"Tentatives : {st.session_state.attempts[ex_id]}")
        if st.session_state[sol_key]:
            st.markdown("### Correction (méthode)")
            st.markdown(ex.get("explanation", ""))
            st.markdown("**Réponse attendue :** " + ", ".join(ex["answer"]))

    else:
        st.info("Type de question non géré.")
def pick_exercise(pool):
    # Prefer unsolved; fallback random
    unsolved = [e for e in pool if e["id"] not in st.session_state.solved]
    candidates = unsolved if unsolved else pool
    return random.choice(candidates) if candidates else None


def reset_progress():
    st.session_state.solved = set()
    st.session_state.attempts = {}
    st.session_state.current_id = None


def get_pool_by_section(exercises, section_name: str):
    """Map tabs/sub-tabs to exercise topics."""
    if section_name == "cr":
        allowed = {"Compte de résultat"}
    elif section_name == "bilan":
        allowed = {"Bilan"}
    elif section_name == "couts":
        allowed = {"Coûts", "Coûts et marges"}
    elif section_name == "marges":
        allowed = {"Marges", "Coûts et marges"}
    elif section_name == "rentab":
        allowed = {"Rentabilité"}
    elif section_name == "valeur":
        allowed = {"Valeur actionnariale / boursière", "Valeur actionnariale", "Valeur boursière"}
    else:
        allowed = {e.get("topic") for e in exercises if e.get("topic")}
    return [e for e in exercises if e.get("topic") in allowed]


def render_section(section_key: str, section_title: str, exercises):
    pool = get_pool_by_section(exercises, section_key)
    if not pool:
        st.warning("Aucun exercice disponible dans cette section.")
        return

    # Keep section-specific current id to avoid confusion when switching tabs
    current_key = f"current_id_{section_key}"
    if current_key not in st.session_state:
        st.session_state[current_key] = None

    colA, colB, colC = st.columns([1.2, 1.2, 1])
    with colA:
        mode = st.radio(
            "Mode",
            ["Aléatoire", "Choisir un exercice"],
            index=0,
            horizontal=True,
            key=f"mode_{section_key}",
        )
    with colB:
        if mode == "Choisir un exercice":
            labels = []
            id_map = {}
            for e in pool:
                lab = e["title"]
                # ensure uniqueness
                if lab in id_map:
                    lab = f"{lab} ({e['id']})"
                labels.append(lab)
                id_map[lab] = e["id"]
            chosen_label = st.selectbox("Exercice", labels, key=f"pick_{section_key}")
            chosen_id = id_map[chosen_label]
            ex = next(e for e in pool if e["id"] == chosen_id)
            st.session_state[current_key] = ex["id"]
        else:
            if st.button("➡️ Nouvel exercice", key=f"new_{section_key}"):
                ex = pick_exercise(pool)
                st.session_state[current_key] = ex["id"]
            else:
                if st.session_state[current_key] is None:
                    ex = pick_exercise(pool)
                    st.session_state[current_key] = ex["id"]
                else:
                    ex = next(e for e in pool if e["id"] == st.session_state[current_key])

    with colC:
        if st.button("🔄 Réinitialiser", key=f"reset_"{section_key}"):
            reset_progress()
            # Also reset per-section current ids
            for k in [f"current_id_"{section_key}"]:
                if k in st.session_state:
                    st.session_state[k] = None
            st.rerun()

    st.markdown(f"## {section_title}")

    # Display exercise
    st.subheader(ex["title"])
    cols = st.columns([1, 1])
    cols[0].markdown(f"**Matière :** {ex['theme']}")
    cols[1].markdown(f"**Thème :** {ex['topic']}")

    with st.expander("📌 Contexte / données", expanded=True):
        st.write(ex.get("context", ""))

    st.markdown("### Question")
    st.write(ex.get("question", ""))

    # Attempts tracking
    st.session_state.attempts.setdefault(ex["id"], 0)

    # Input + check (selon le type de question)
    render_question(ex, section_key)

def main():
    st.set_page_config(page_title=APP_TITLE, layout="centered")

    # Branding (assets in project folder)
    banner_path = Path(__file__).parent / "Banniere_Askip.png"
    logo_path = Path(__file__).parent / "LOGO_anime_App.gif"
    if banner_path.exists():
        st.image(str(banner_path), use_container_width=True)
    init_state()

    st.title(APP_TITLE)
    st.caption("Entraînement interactif : compte de résultat, bilan, coûts, marges, rentabilité…")

    exercises = load_exercises()
    total = len(exercises)
    solved = len(st.session_state.solved)

    # Progress on top
    m1, m2 = st.columns([1, 1])
    m1.metric("Progression", f"{solved}/{total}")
    m2.metric("Objectif", "Savoir choisir les bonnes données")

    tab_cr, tab_bilan, tab_calc = st.tabs(["📒 Compte de résultat", "📗 Bilan", "🧾 Calculs"])

    with tab_cr:
        render_section("cr", "Compte de résultat", exercises)

    with tab_bilan:
        render_section("bilan", "Bilan", exercises)

    with tab_calc:
        sub1, sub2, sub3, sub4 = st.tabs(["🧾 Coûts", "📈 Marges", "📊 Rentabilité", "💡 Valeur"])
        with sub1:
            render_section("couts", "Coûts", exercises)
        with sub2:
            render_section("marges", "Marges", exercises)
        with sub3:
            render_section("rentab", "Rentabilité", exercises)
        with sub4:
            render_section("valeur", "Valeur actionnariale / boursière", exercises)

    st.markdown ("---")

    col1, col2, col3 = st.columns ([1, 1, 1])
    with col2:
        if logo_path.exists():
            st.image(str(logo_path), width=90)

    st.caption("© Sandrine Lefebvre-Reghay - Usage pédagogique — Askip’en STMG Calculs")


if __name__ == "__main__":
    main()
