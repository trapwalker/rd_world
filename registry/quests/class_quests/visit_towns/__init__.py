# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnEnterToLocation, OnNote
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import ListField, RegistryLinkField, LocalizedString

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestVisitTowns(ClassTypeQuest):
    towns = ListField(
        caption=u"Города, которые нужно посетить",
        field=RegistryLinkField(document_type='sublayers_server.model.registry_me.classes.poi.Town'),
    )

    def init_text(self):
        self.text = LocalizedString(_id="q_cq_journal_text").generate(
            player_name=self.agent.login, task_text=self.locale("q_cq_visit_towns_task_text"))  ##LOCALIZATION

    def visit_town(self, event, town):
        town_uri = town.uri
        if town in self.towns and self.dc.visited_towns.get(town.uri, None) is None:
            self.dc.visited_towns[town_uri] = True
            towns_left = len(self.towns) - len(self.dc.visited_towns.keys())
            text = LocalizedString(_id='q_cq_visit_towns_visit_one_template').generate(town=town, towns_left=towns_left)  ##LOCALIZATION
            self.log(text=text, event=event)
            if towns_left == 0:
                self.log(text=self.locale("q_cq_visit_towns_replica_return_to_teacher"), event=event)

    def on_start_(self, event, **kw):
        self.init_text()
        self.dc.visited_towns = dict()
        self.log(text=self.locale("q_cq_visit_towns_started"), event=event)  ##LOCALIZATION


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.visited_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.VisitTownsQuestNote,
                time=event.time,
                page_caption=quest.locale("q_cq_visit_towns_finished_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_visit_towns_finished_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )
            # Защитать текущий город
            quest.visit_town(event=event, town=quest.hirer.hometown)

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.visited_note):
                if len(quest.towns) == len(quest.dc.visited_towns.keys()):
                    quest.agent.profile.del_note(uid=quest.dc.visited_note, time=event.time)
                    quest.go(event=event, new_state="win")  # Все города посещены!
                else:
                    text = LocalizedString(_id="q_cq_visit_towns_replica_not_finish").generate(  ##LOCALIZATION
                        towns_left=len(quest.towns) - len(quest.dc.visited_towns.keys()),
                    )
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=text,
                        event=event
                    )

            if isinstance(event, OnEnterToLocation):
                quest.visit_town(event=event, town=event.location.example)
                # todo: Возможно проверить, а не посещены ли все города и выдать следующий квест


    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.npc_replica(
                npc=quest.hirer,
                replica=quest.locale("q_cq_visit_towns_phrase_success"),  ##LOCALIZATION
                event=event
            )
            quest.log(text=quest.locale("q_cq_visit_towns_finished"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
