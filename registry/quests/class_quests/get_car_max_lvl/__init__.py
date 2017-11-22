# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnNote
from sublayers_server.model.registry_me.classes import notes
from functools import partial
from sublayers_server.model.registry_me.tree import LocalizedString, Subdoc, RegistryLinkField, MapField, EmbeddedDocumentField

from sublayers_world.registry.quests.class_quests import ClassTypeQuest



class GetCarMaxLevelQuest(ClassTypeQuest):

    class RoleClassQuestAttributes(Subdoc):
        next_quest = RegistryLinkField(
            caption=u"Прототип классового квеста",
            document_type='sublayers_server.model.registry_me.classes.quests.Quest',
            root_default='reg:///registry/quests/class_quests/start_quest'
        )

    attributes_by_class = MapField(
        caption=u'Словарь атрибутов',
        field=EmbeddedDocumentField(document_type=RoleClassQuestAttributes),
    )
    ####################################################################################################################
    def init_text(self):
        self.text = LocalizedString(_id="q_cq_get_car_lvl_text")  ##LOCALIZATION

    def on_start_(self, event, **kw):
        role_class = self.agent.profile.role_class
        class_attrs = self.attributes_by_class.get(role_class.name, None)
        self.next_quest = class_attrs.next_quest

        self.init_text()
        self.log(text=self.locale("q_cq_get_car_lvl_started"), event=event)  ##LOCALIZATION


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.car_info_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.GetMaxCarLvlQuestNote,
                time=event.time,
                page_caption=quest.locale("q_cq_get_car_lvl_note_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_get_car_lvl_note_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.car_info_note):
                agent = quest.agent.profile
                if agent.car and agent.car.get_real_lvl() > 4: # info по идее это максимальный уровень машинки
                    agent.del_note(uid=quest.dc.car_info_note, time=event.time)
                    quest.go(event=event, new_state="win")
                else:
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=quest.locale("q_cq_get_car_lvl_bad"),  ##LOCALIZATION
                        event=event
                    )


    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.npc_replica(
                npc=quest.hirer,
                replica=quest.locale("q_cq_get_car_lvl_phrase_success"),  ##LOCALIZATION
                event=event
            )
            quest.log(text=quest.locale("q_cq_get_car_lvl_finished"), event=event)  # ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
