from copy import deepcopy
from utilities.Message import Message


def prune_context(messages, max_chars=40000, save_to_longterm = None):
    """
    Prunes mid-conversation history if total characters exceed max_chars.
    Protects: System prompts, the very first user prompt, and the 3 most recent messages.
    Trims content within a message if a single intermediate message is huge.
    """

    # If no savefunc is given, use a lambda that does nothing
    save_to_longterm = save_to_longterm or (lambda *args, **kwargs: None)

    # Quick character count estimation
    def get_total_chars(msgs):
        return sum(len(str(m.get("content") or "")) for m in msgs)
    
    if get_total_chars(messages) <= max_chars:
        return messages

    # Deep copy to avoid modifying data permanently out of scope
    pruned = deepcopy(messages)
    
    # Identify protected indices
    protected_indices = set()
    
    # 1. Protect system prompts and the very first non-system prompt (the initial prompt)
    for i, msg in enumerate(pruned):
        if msg.get("role") == "system":
            protected_indices.add(i)

        
    # 2. Protect the LATEST user prompt (scan backwards from the end)
    for i in range(len(pruned) - 1, -1, -1):
        if pruned[i].get("role") == "user":
            protected_indices.add(i)
            break # Stop after finding the closest user prompt
    
    # 3. Protect the most recent context loop elements (e.g., last 3 messages)
    recent_indices = []
    recent_count = min(3, len(pruned))
    for i in range(len(pruned) - recent_count, len(pruned)):
        if i not in protected_indices:  # Don't overlap with system or latest user prompt
            protected_indices.add(i)
            recent_indices.append(i)

    # 4. Evict or truncate middle unprotected messages until under limit
    i = 0
    while i < len(pruned) and get_total_chars(pruned) > max_chars:
        if i in protected_indices:
            i += 1
            continue
            
        content = str(pruned[i].get("content") or "")
        # Cut down massive individual middle messages (Keep the END)
        if len(content) > 2000:
            
            save_to_longterm(Message(role=pruned[i]["role"], content=pruned[i]["content"]))
            
            pruned[i]["content"] = "... [Truncated Start] ... " + content[-1000:]
            if get_total_chars(pruned) <= max_chars:
                break
        
        else:
            save_to_longterm(Message(role=pruned[i]["role"], content=pruned[i]["content"]))


        # If still over limit, evict the entire message row
        pruned.pop(i)
        # Recalculate shifted tracking indices
        protected_indices = {idx - 1 if idx > i else idx for idx in protected_indices}
        recent_indices = [idx - 1 if idx > i else idx for idx in recent_indices]
        
    # 5. Emergency fallback if recent messages alone violate max_chars
    # Truncate large recent messages (keep the end) or pop small ones
    if get_total_chars(pruned) > max_chars:
        # Sort in reverse order (newest to oldest) to pop elements safely without messing up preceding loop indices
        recent_indices.sort(reverse=True) 
        
        for idx in recent_indices:
            if get_total_chars(pruned) <= max_chars:
                break
                
            content = str(pruned[idx].get("content") or "")
            role =  str(pruned[idx].get("role") or "")

            save_to_longterm(Message(role=role, content=content))

            if len(content) > 500:
                # If large, keep only the last 200 characters
                pruned[idx]["content"] = "... [Emergency Truncate Start] ... " + content[-200:]
            else:
                # NEW: If small, completely evict the message
                pruned.pop(idx)
    
    if get_total_chars(pruned) > max_chars:
        raise Exception("error non evictable context too big to fit")


    return pruned
