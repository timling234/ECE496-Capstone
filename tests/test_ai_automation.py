"""Offline execution acceptance: group atomicity, stale edits and human control."""
from contextlib import closing
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock
from src.ai_automation import AutomationReviewer
from src.ai_settings import save,settings
from src.review_ai import POLICY
from src.store_poc import store,process_stored
from src.web_editorial import initialize,create_announcement,items,publishable,decide,edit_announcement


class AutomationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.db=Path(temp.name)/'asap.sqlite3'
        with closing(sqlite3.connect(self.db)) as conn:
            store(conn,[]);process_stored(conn);conn.commit();initialize(conn);conn.commit()
        self.model=Mock(ready=True,model='fixture',policy=POLICY)
        self.model.review.return_value={'recommendation':'approve','reason':'Clear announcement.'}
        self.model.generate.return_value={'selected':'1','decisions':[{'item':'1','recommendation':'approve','reason':'Best complete original.'},{'item':'2','recommendation':'reject','reason':'Duplicate of the selected original.'}]}
        self.reviewer=AutomationReviewer(self.model);self.reviewer.recover(self.db)

    def add(self,text='Date: November 11, 2026. Public seminar at 3 PM.'):
        with closing(sqlite3.connect(self.db)) as conn:return create_announcement(conn,text,actor='alice')

    def configure(self,approve=True,reject=True):
        with closing(sqlite3.connect(self.db)) as conn:save(conn,dict(model='fixture',policy=POLICY,auto_approve='on' if approve else '',auto_reject='on' if reject else '',batch_limit=20),{'fixture':0})

    def finish(self):
        self.assertTrue(self.reviewer.slot.acquire(timeout=3));self.reviewer.slot.release()

    def test_defaults_are_advice_only_and_single_post_can_be_auto_approved(self):
        post_id=self.add()
        with self.assertRaises(ValueError):self.reviewer.run_batch(self.db,'alice','automatic')
        self.configure()
        self.reviewer.run_batch(self.db,'alice','automatic');self.finish()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(len(publishable(conn)),1)
            self.assertEqual(conn.execute('SELECT actor FROM editorial_decisions').fetchone()[0],'ai:alice')
            self.assertEqual(conn.execute('SELECT action,reason FROM ai_automation_actions').fetchone(),('approve','Clear announcement.'))
            self.assertEqual(conn.execute('SELECT applied FROM ai_batches').fetchone()[0],1)
            decide(conn,'manual',post_id,'reject',actor='alice')
            self.assertEqual(publishable(conn),[])
            self.assertEqual(conn.execute('SELECT actor FROM editorial_decisions').fetchone()[0],'alice')

    def test_duplicate_group_advice_and_atomic_execution_publish_one_only(self):
        one=self.add();self.add()
        self.reviewer.submit(self.db,'manual',one,'alice');self.finish()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ai_suggestions WHERE status='complete'").fetchone()[0],2)
            self.assertEqual(publishable(conn),[])
        self.model.generate.assert_called_once()
        self.configure()
        self.reviewer.run_batch(self.db,'alice','automatic');self.finish()
        self.model.generate.assert_called_once()  # Reuse the group advice.
        with closing(sqlite3.connect(self.db)) as conn:
            states=[p['editorial_status'] for p in items(conn)]
            self.assertCountEqual(states,['approved','rejected'])
            self.assertEqual(len(publishable(conn)),1)
            from src.review_ai import attach
            reviewed=items(conn);attach(conn,reviewed,True)
            self.assertFalse(any(p['ai_review']['stale'] for p in reviewed))
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM ai_automation_actions').fetchone()[0],2)
            self.assertEqual(conn.execute('SELECT applied FROM ai_batches ORDER BY id DESC LIMIT 1').fetchone()[0],2)

    def test_uncertain_group_and_approve_only_setting_cannot_reject_alternatives(self):
        self.add();self.add();self.configure(approve=True,reject=False)
        self.reviewer.run_batch(self.db,'alice','automatic');self.finish()
        with closing(sqlite3.connect(self.db)) as conn:self.assertTrue(all(p['editorial_status']=='pending' for p in items(conn)))
        self.configure()
        self.model.generate.return_value={'selected':None,'decisions':[{'item':'1','recommendation':'needs_review','reason':'Dates differ.'},{'item':'2','recommendation':'needs_review','reason':'Could be a distinct event.'}]}
        # New policy invalidates the previous cached approval.
        with closing(sqlite3.connect(self.db)) as conn:conn.execute("UPDATE ai_settings SET policy=policy||' Evaluate dates carefully.'");conn.commit()
        self.reviewer.run_batch(self.db,'alice','automatic');self.finish()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(publishable(conn),[])
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM ai_automation_actions').fetchone()[0],0)

    def test_reject_all_duplicate_group(self):
        self.add();self.add();self.configure(approve=False,reject=True)
        self.model.generate.return_value={'selected':None,'decisions':[{'item':str(i),'recommendation':'reject','reason':'Clear spam.'} for i in (1,2)]}
        self.reviewer.run_batch(self.db,'alice','automatic');self.finish()
        with closing(sqlite3.connect(self.db)) as conn:self.assertTrue(all(p['editorial_status']=='rejected' for p in items(conn)))

    def test_inconsistent_group_model_output_cannot_execute(self):
        self.add();self.add();self.configure()
        self.model.generate.return_value={'selected':'1','decisions':[{'item':str(i),'recommendation':'approve','reason':'Approve both.'} for i in (1,2)]}
        self.reviewer.run_batch(self.db,'alice','automatic');self.finish()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(publishable(conn),[])
            self.assertEqual(conn.execute('SELECT status FROM ai_batches').fetchone()[0],'complete_with_errors')

    def test_human_decision_during_inference_prevents_automatic_change(self):
        post=self.add();self.configure();started=threading.Event();release=threading.Event()
        def wait_for_human(p):started.set();release.wait(3);return dict(recommendation='approve',reason='Clear announcement.')
        self.model.review.side_effect=wait_for_human
        self.reviewer.run_batch(self.db,'alice','automatic');self.assertTrue(started.wait(2))
        with closing(sqlite3.connect(self.db)) as conn:decide(conn,'manual',post,'reject',actor='alice')
        release.set();self.finish()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(items(conn)[0]['editorial_status'],'rejected')
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM ai_automation_actions').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT status FROM ai_suggestions').fetchone()[0],'stale')

    def test_policy_or_settings_change_during_inference_prevents_execution(self):
        self.add();self.configure();started=threading.Event();release=threading.Event()
        def blocked(p):started.set();release.wait(3);return dict(recommendation='approve',reason='Clear.')
        self.model.review.side_effect=blocked
        self.reviewer.run_batch(self.db,'alice','automatic');self.assertTrue(started.wait(2))
        self.configure(approve=False,reject=False);release.set();self.finish()
        with closing(sqlite3.connect(self.db)) as conn:self.assertEqual(publishable(conn),[])

    def test_stopping_running_batch_prevents_current_action(self):
        self.add();self.configure();started=threading.Event();release=threading.Event()
        def blocked(p):started.set();release.wait(3);return dict(recommendation='approve',reason='Clear.')
        self.model.review.side_effect=blocked
        batch=self.reviewer.run_batch(self.db,'alice','automatic');self.assertTrue(started.wait(2))
        self.reviewer.cancel(self.db,batch);release.set();self.finish()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('SELECT status FROM ai_batches').fetchone()[0],'cancelled')
            self.assertEqual(publishable(conn),[])
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM ai_automation_actions').fetchone()[0],0)

    def test_existing_human_approval_in_group_is_not_replaced(self):
        one=self.add();self.add();self.configure()
        with closing(sqlite3.connect(self.db)) as conn:decide(conn,'manual',one,'approve',actor='alice')
        self.reviewer.submit(self.db,'manual',one,'alice');self.finish()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(publishable(conn)[0]['post_id'],one)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM ai_automation_actions').fetchone()[0],0)

    def test_new_duplicate_can_be_rejected_while_preserving_published_representative(self):
        original=self.add();self.add();self.configure(approve=False,reject=True)
        with closing(sqlite3.connect(self.db)) as conn:
            decide(conn,'manual',original,'approve',actor='alice')
            # A newly discovered duplicate enters the queue after publication.
            new=self.add()
            conn.execute("DELETE FROM editorial_decisions WHERE post_id!=?",(original,));conn.commit()
            ordered=sorted(items(conn),key=lambda p:(p['platform'],p['post_id']))
        winner=str(next(i+1 for i,p in enumerate(ordered) if p['post_id']==original))
        self.model.generate.return_value={'selected':winner,'decisions':[{'item':str(i+1),'recommendation':'approve' if p['post_id']==original else 'reject','reason':'Keep published original.' if p['post_id']==original else 'New duplicate.'} for i,p in enumerate(ordered)]}
        self.reviewer.run_batch(self.db,'alice','automatic');self.finish()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual([p['post_id'] for p in publishable(conn)],[original])
            self.assertEqual(conn.execute('SELECT actor FROM editorial_decisions WHERE post_id=?',(original,)).fetchone()[0],'alice')
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ai_automation_actions WHERE action='approve'").fetchone()[0],0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ai_automation_actions WHERE action='reject'").fetchone()[0],2)

    def test_group_execution_rolls_back_all_items_on_database_failure(self):
        self.add();self.add();self.configure()
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("CREATE TRIGGER prevent_ai_audit BEFORE INSERT ON ai_automation_actions BEGIN SELECT RAISE(ABORT,'fixture'); END");conn.commit()
        self.reviewer.run_batch(self.db,'alice','automatic');self.finish()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertTrue(all(p['editorial_status']=='pending' for p in items(conn)))
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM ai_automation_actions').fetchone()[0],0)

    def test_wrong_workspace_and_invalid_mode_are_rejected(self):
        post=self.add()
        with self.assertRaises(ValueError):self.reviewer.submit(self.db,'manual','unknown','alice')
        with self.assertRaises(ValueError):self.reviewer.run_batch(self.db,'alice','publish-everything')
        self.model.review.assert_not_called()
