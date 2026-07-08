# Last updated: 2026-07-08 22:03:10
# @nova: nova_runtime — Nova's life-support engine (runtime / layer 2 of the three-layer
#        model). Brings up and holds what keeps her alive and thinking, independent of any
#        interaction surface: the event bus (publish-to-faces), the transcript store
#        (perceive Cole without depending on the chat server), and — as the extraction
#        proceeds — her model client, memory indexer, sense population, llama health, and
#        KoELS loadout equip. Pluck every face and this layer still runs.
from nova_runtime.event_bus import EventBus
from nova_runtime.transcript_store import TranscriptStore
from nova_runtime.runtime import NovaRuntime

__all__ = ["EventBus", "TranscriptStore", "NovaRuntime"]
