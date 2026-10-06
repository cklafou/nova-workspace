# Last updated: 2026-10-06 03:45:20
# @nova: Verify pending-input inspection cannot mutate, consume or acknowledge a body conversation queue.
import asyncio
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nova_runtime.conversation import ActiveTurn


class UncopyableOwner:
    def __deepcopy__(self, memo):
        raise AssertionError("Opaque transport ownership must retain its identity")


class PendingInspectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_defends_content_and_metadata_without_applying_or_consuming(self):
        observed=[]
        async def applied(entries, revision):observed.append((entries,revision))
        turn=ActiveTurn(on_apply=applied);owner=UncopyableOwner()
        turn.push([{'content':[{'type':'text','text':'Use no tools.'}], 'owner':owner,
                    'request_id':'first','metadata':{'labels':['original']}}])
        turn.push([{'content':'Finish the same request.','request_id':'second'}])
        snapshot=turn.pending_inputs()
        self.assertEqual((turn.revision,turn.applied_revision),(2,0))
        self.assertEqual(observed,[])
        self.assertTrue(turn.pending)
        self.assertIs(snapshot[0]['owner'],owner)
        snapshot[0]['content'][0]['text']='mutated'
        snapshot[0]['metadata']['labels'].append('mutated')
        snapshot[0]['request_id']='changed'
        snapshot.reverse();snapshot.pop()
        saved=turn.pending_inputs()
        self.assertEqual([entry['request_id'] for entry in saved],['first','second'])
        self.assertEqual(saved[0]['content'][0]['text'],'Use no tools.')
        self.assertEqual(saved[0]['metadata'],{'labels':['original']})
        self.assertFalse(turn.try_seal())
        self.assertEqual(observed,[])
        batch,revision=await turn.consume()
        self.assertEqual(revision,2)
        self.assertEqual(turn.applied_revision,2)
        self.assertEqual([entry['request_id'] for entry in batch],['first','second'])
        self.assertEqual(len(observed),1)
        self.assertFalse(turn.pending)
        self.assertEqual(turn.pending_inputs(),[])

    async def test_prior_snapshot_is_stable_when_new_input_arrives_or_turn_closes(self):
        turn=ActiveTurn();turn.push([{'content':'First'}])
        first=turn.pending_inputs();turn.push([{'content':'Second'}])
        self.assertEqual([entry['content'] for entry in first],['First'])
        pending=turn.close()
        self.assertEqual([entry['content'] for entry in pending],['First','Second'])
        self.assertEqual(turn.pending_inputs(),[])
        self.assertEqual((turn.revision,turn.applied_revision),(2,0))
        self.assertFalse(turn.can_accept)

if __name__=='__main__':unittest.main()
