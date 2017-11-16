# -*- coding: utf-8 -*-
import logging

from setuptools.command.test import test

log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import Quest, QuestState_, WinState
from sublayers_server.model.quest_events import OnExitFromLocation, OnNote
from sublayers_server.model.registry_me.classes import notes
from functools import partial
from sublayers_server.model.registry_me.tree import (
    Subdoc, LocalizedString,
    MapField, ListField,
    LocalizedStringField,
    EmbeddedDocumentField,
    RegistryLinkField,
)

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class GetClassCarQuest(ClassTypeQuest):
    class RoleClassQuestAttributes(Subdoc):
        car_list = ListField(
            caption=u"Список классовых машин",
            field=RegistryLinkField(
                document_type='sublayers_server.model.registry_me.classes.mobiles.Mobile',
            ),
        )

    attributes_by_class = MapField(
        caption=u'Словарь атрибутов',
        field=EmbeddedDocumentField(document_type=RoleClassQuestAttributes),
    )

    def init_text(self):
        self.text = LocalizedString(_id='q_cq_get_car_text_template').generate(role_class_name=self.locale(self.agent.profile.role_class.title))  ##LOCALIZATION

    def on_start_(self, event, **kw):
        self.init_text()
        self.log(text=self.locale("q_cq_get_car_started"), event=event)  ##LOCALIZATION
        # todo: как-то сообщить пользователю на каких тачках нужно приезжать.


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.car_info_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.GetClassCarQuestNote,
                time=event.time,
                page_caption=quest.locale("q_cq_get_car_note_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_get_car_note_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            agent = quest.agent.profile
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.car_info_note):
                role_class = quest.agent.profile.role_class
                attributes_of_class = role_class and quest.attributes_by_class.get(role_class.name, None)
                if attributes_of_class is None:
                    log.warning(u'Unsupported role class by class quest: {}'.format(role_class.name))
                else:
                    if agent.car:
                        for candidate in attributes_of_class.car_list:
                            if agent.car.is_ancestor(candidate):
                                agent.del_note(uid=quest.dc.car_info_note, time=event.time)
                                quest.npc_replica(
                                    npc=quest.hirer,
                                    replica=quest.locale("q_cq_get_car_note_phrase_success"),  ##LOCALIZATION
                                    event=event
                                )
                                quest.go(event=event, new_state="win")
                                return
                        text = LocalizedString(_id="q_cq_get_car_not_u_cl").generate(  ##LOCALIZATION
                            classname=quest.locale(quest.agent.profile.role_class.title),
                        )
                        quest.npc_replica(
                            npc=quest.hirer,
                            replica=text,
                            event=event
                        )
                    else:
                        quest.npc_replica(
                            npc=quest.hirer,
                            replica=quest.locale("q_cq_get_car_not_car"),  ##LOCALIZATION
                            event=event
                        )


    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_cq_get_car_finished"), event=event)  # ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
