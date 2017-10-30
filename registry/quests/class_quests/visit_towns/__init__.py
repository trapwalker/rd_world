# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnEnterToLocation, OnNote
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import (
    ListField,
    RegistryLinkField,
)

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestVisitTowns(ClassTypeQuest):
    towns = ListField(
        caption=u"Города, которые нужно посетить",
        field=RegistryLinkField(document_type='sublayers_server.model.registry_me.classes.poi.Town'),
    )

    def init_text(self):
        pass

    def visit_town(self, event, town):
        town_uri = event.location.example.uri
        if town in self.towns and self.dc.visited_towns.get(town.uri, None):
            self.dc.visited_towns[town_uri] = True

            l_visited = len(self.dc.visited_towns.keys())
            l_need_visit = len(self.towns)
            self.log(text=self.locale("{} visited! {} left.".format(
                self.locale(town.title),
                l_need_visit - l_visited)
            ), event=event)  # todo: ##LOCALIZATION

    def on_start_(self, event, **kw):
        self.init_text()
        self.dc.visited_towns = dict()
        self.log(text=self.locale("q_cq_started"), event=event)  # todo: ##LOCALIZATION


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.car_info_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.NPCPageNote,
                time=event.time,
                page_caption=quest.locale("ClassQuestVisitTowns Page caption"),  # todo: ##LOCALIZATION
                btn1_caption=quest.locale("ClassQuestVisitTowns btn caption"),  # todo: ##LOCALIZATION
                npc=quest.hirer,
            )
            # Защитать текущий город
            quest.visit_town(event=event, town=quest.hirer.hometown)

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.car_info_note):
                if len(quest.towns) == len(quest.dc.visited_towns.keys()):
                    quest.log(text=quest.locale("All towns visited!"), event=event)  # todo: ##LOCALIZATION
                    quest.go(event=event, new_state="win")  # Все города посещены!
                else:
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=quest.locale("ClassQuestVisitTowns Visit all Towns!"),  # todo: ##LOCALIZATION
                        event=event
                    )

            if isinstance(event, OnEnterToLocation):
                quest.visit_town(event=event, town=event.location.example)
                # todo: Возможно проверить, а не посещены ли все города и выдать следующий квест


    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_cq_final"), event=event)  # todo: ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
