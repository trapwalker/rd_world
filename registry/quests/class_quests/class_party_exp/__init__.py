# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnNote, OnPartyExp
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField, LocalizedString

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestPartyExp(ClassTypeQuest):
    exp_value = IntField(caption=u"Сумма опыта для накопления")

    def init_text(self):
        pass

    def on_start_(self, event, **kw):
        self.init_text()
        self.dc.exp_summ = 0
        self.log(text=self.locale("q_cq_party_exp_started"), event=event)  ##LOCALIZATION


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.quest_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.GetPartyExpQuestNote,
                time=event.time,
                page_caption=quest.locale("q_cq_party_exp_finished_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_party_exp_finished_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                if quest.dc.exp_summ >= quest.exp_value:
                    quest.agent.profile.del_note(uid=quest.dc.quest_note, time=event.time)
                    quest.go(event=event, new_state="win")
                else:
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=quest.locale("q_cq_party_exp_replica_not_finish"),  ##LOCALIZATION
                        event=event
                    )

            if isinstance(event, OnPartyExp) and event.agents and quest.agent.profile._agent_model in event.agents:
                quest.dc.exp_summ += event.exp
                text = LocalizedString(_id='q_cq_party_exp_one_template').generate(
                    exp=quest.dc.exp_summ,
                    max_exp=quest.exp_value)  ##LOCALIZATION
                quest.log(text=text, event=event)
                if quest.dc.exp_summ >= quest.exp_value:
                    quest.log(text=quest.locale("q_cq_party_exp_done_text"), event=event)  ##LOCALIZATION


    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_cq_party_exp_finished"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
