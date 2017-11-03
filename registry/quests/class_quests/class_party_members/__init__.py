# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnNote, OnPartyInclude
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField, LocalizedString

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestPartyMembers(ClassTypeQuest):
    members_count = IntField(caption=u"Количество игроков, необходимое в пати")

    def init_text(self):
        pass

    def on_start_(self, event, **kw):
        self.init_text()
        self.dc.max_count = 0  # Максимальное кол-во людей в пати
        self.log(text=self.locale("q_cq_party_members_started"), event=event)  ##LOCALIZATION

    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.quest_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.NPCPageNote,
                time=event.time,
                page_caption=quest.locale("q_cq_party_members_finished_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_party_members_finished_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                if quest.members_count <= quest.dc.max_count:
                    quest.go(event=event, new_state="back_to_teacher")
                else:
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=quest.locale("q_cq_party_members_replica_not_finish"),  ##LOCALIZATION
                        event=event
                    )

            if isinstance(event, OnPartyInclude):
                q_agent = quest.agent.profile._agent_model
                in_agent = event.agent
                if q_agent and q_agent.party and in_agent and in_agent.party is q_agent.party and in_agent.party.owner is q_agent:
                    quest.dc.max_count = max(quest.dc.max_count, len(q_agent.party.members))
                if quest.members_count <= quest.dc.max_count:
                    quest.log(text=quest.locale("q_cq_party_members_back_to_teacher"), event=event)  ##LOCALIZATION
                    quest.go(event=event, new_state="back_to_teacher")

    class back_to_teacher(QuestState_):
        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                # todo: убрать потом, когда придумаем другую заглушку
                quest.npc_replica(
                    npc=quest.hirer,
                    replica="Дальше пока не сделано. Нужно подождать.",
                    event=event
                )
                # quest.agent.profile.del_note(uid=quest.dc.quest_note, time=event.time)
                # quest.go(event=event, new_state="win")

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_cq_party_members_finished"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
