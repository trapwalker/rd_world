# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnNote, OnBarterSuccess
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField, LocalizedString

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestBarterCount(ClassTypeQuest):
    barters_count = IntField(caption=u"Количество завершённых бартеров")

    def init_text(self):
        self.text = LocalizedString(_id="q_cq_journal_text").generate(
            player_name=self.agent.login, task_text=self.locale("q_cq_barters_task_text"))  ##LOCALIZATION

    def on_start_(self, event, **kw):
        self.init_text()
        self.dc.barter_agents = []  # Список uid с кем были бартеры
        self.log(text=self.locale("q_cq_barters_started"), event=event)  ##LOCALIZATION

    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.quest_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.BarterSuccessQuestNote,
                time=event.time,
                page_caption=quest.locale("q_cq_barters_finished_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_barters_finished_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                if quest.barters_count <= len(quest.dc.barter_agents):
                    quest.go(event=event, new_state="back_to_teacher")
                else:
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=quest.locale("q_cq_barters_replica_not_finish"),  ##LOCALIZATION
                        event=event
                    )

            if isinstance(event, OnBarterSuccess):
                q_agent = quest.agent.profile._agent_model
                second_agent = event.barter.recipient if q_agent is event.barter.initiator else event.barter.initiator
                if second_agent and second_agent.uid not in quest.dc.barter_agents:
                    quest.dc.barter_agents.append(second_agent.uid)
                    text = LocalizedString(_id='q_cq_barters_add_one').generate(
                        agent_login=second_agent.print_login())  ##LOCALIZATION
                    quest.log(text=text, event=event)
                    if quest.barters_count <= len(quest.dc.barter_agents):
                        quest.log(text=quest.locale("q_cq_barters_back_to_teacher"), event=event)  ##LOCALIZATION
                        quest.go(event=event, new_state="back_to_teacher")

    class back_to_teacher(QuestState_):
        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                quest.agent.profile.del_note(uid=quest.dc.quest_note, time=event.time)
                quest.go(event=event, new_state="win")

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.npc_replica(
                npc=quest.hirer,
                replica=quest.locale("q_cq_barters_phrase_success"),  ##LOCALIZATION
                event=event
            )
            quest.log(text=quest.locale("q_cq_barters_finished"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
