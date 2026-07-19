"""Shared rendering for recommended Azure Policy lists.

Renders each policy's readable name, a meaningful description (or a category
hint when the Azure-provided description is just a stub that repeats the name,
as is the case for ``CMA_*`` Regulatory Compliance manual-attestation
controls), a docs deep link, and the muted GUID.
"""

from typing import Any, Dict, List

import streamlit as st

_INDENT = "&nbsp;&nbsp;&nbsp;&nbsp;"


def _category_hint(pd: Dict[str, Any]) -> str:
    """A short, human note to show when there is no useful description."""
    category = (pd.get("category") or "").strip()
    if category.casefold() == "regulatory compliance":
        return "Regulatory Compliance - manual attestation control (no enforcement logic)"
    if category:
        return f"Category: {category}"
    return ""


def render_policy_list(api_client, policy_ids: List[str]) -> None:
    """Render a bulleted list of policy details for the given GUIDs.

    Details are fetched once per unique id-set and cached in session state so
    reruns don't re-hit the backend.
    """
    if not policy_ids:
        return

    cache_key = f"_policy_detail_cache_{hash(tuple(policy_ids))}"
    if cache_key not in st.session_state:
        try:
            st.session_state[cache_key] = (
                api_client.get_policy_details(policy_ids).get("policies", {})
            )
        except Exception:
            st.session_state[cache_key] = {}
    details = st.session_state[cache_key]

    for policy_id in policy_ids:
        pd = details.get(policy_id)
        if not (pd and pd.get("display_name")):
            st.code(policy_id, language="text")
            continue

        title = f"**{pd['display_name']}**"
        url = pd.get("learn_url", "")
        if url:
            title += f" ([docs]({url}))"
        st.markdown(f"- {title}")

        description = (pd.get("description") or "").strip()
        if description and not pd.get("description_is_stub"):
            st.caption(f"{_INDENT}{description}")
        else:
            hint = _category_hint(pd)
            if hint:
                st.caption(f"{_INDENT}_{hint}_")

        st.caption(f"{_INDENT}`{policy_id}`")
