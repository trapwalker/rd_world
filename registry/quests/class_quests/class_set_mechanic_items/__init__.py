# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnNote
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField, LocalizedString

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestSetMechanicItems(ClassTypeQuest):
    count_items = IntField(caption=u"Количество айтемов механика")

    def init_text(self):
        self.text = LocalizedString(_id="q_cq_journal_text").generate(
            player_name=self.agent.login, task_text=self.locale("q_cq_mech_items_task_text"))  ##LOCALIZATION

    def on_start_(self, event, **kw):
        self.init_text()
        self.log(text=self.locale("q_cq_mech_items_started"), event=event)  ##LOCALIZATION


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.quest_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.SetMechanicItemsQuestNote,
                time=event.time,
                page_caption=quest.locale("q_cq_mech_items_finished_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_mech_items_finished_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note) and quest.agent.profile.car:
                mec_items_len = len(quest.agent.profile.car.iter_mechanic_items())
                if mec_items_len >= quest.count_items:
                    quest.agent.profile.del_note(uid=quest.dc.quest_note, time=event.time)
                    quest.go(event=event, new_state="win")
                else:
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=LocalizedString(_id='q_cq_mech_items_replica_not_fin').generate(
                            left=quest.count_items - mec_items_len),  ##LOCALIZATION
                        event=event
                    )


    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_cq_mech_items_finished"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
