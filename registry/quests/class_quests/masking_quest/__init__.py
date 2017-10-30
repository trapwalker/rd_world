# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState, QuestRange
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


class MaskingQuest(ClassTypeQuest):
    radius_range = EmbeddedDocumentField(document_type=QuestRange, reinst=True)

    class RoleClassQuestAttributes(Subdoc):
        next_quest = RegistryLinkField(
            caption=u"Прототип классового квеста",
            document_type='sublayers_server.model.registry_me.classes.quests.Quest',
            root_default='reg:///registry/quests/class_quests/start_quest'
        )
        class_item = RegistryLinkField(
            document_type='sublayers_server.model.registry_me.classes.quest_item.QuestItem',
        )

    attributes_by_class = MapField(
        caption=u'Словарь атрибутов',
        field=EmbeddedDocumentField(document_type=RoleClassQuestAttributes),
    )

    def init_text(self):
        pass

    def on_start_(self, event, **kw):
        # Определяем следующий квест
        role_class = self.agent.profile.role_class
        class_attrs = self.attributes_by_class.get(role_class.name, None)
        self.next_quest = class_attrs.next_quest

        self.init_text()
        self.log(text=self.locale("q_cq_started"), event=event)  ##LOCALIZATION

        # Выдаем классовый предмет
        # class_attrs = quest.attributes_by_class.get(agent.role_class.name, None)
        # if class_attrs:
        #     class_item = class_attrs.class_item.instantiate()
        #     agent.quest_inventory.add_item(agent=quest.agent, item=class_item, event=event)
        # else:
        #     log.warninig('role class %r is not supported in ClassQuest', agent.role_class)
        #     return




    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.masking_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.MaskingTastQuestNote,
                time=event.time,
                page_caption=quest.locale("q_GetClassCarQuestNote Page caption"),
                btn1_caption=quest.locale("q_GetClassCarQuestNote btn caption"),
                npc=quest.hirer,
            )

            quest.set_timer(event=event, name='test_delivery_cache_quest', delay=5)

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent.profile
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.car_info_note):
                role_class = quest.agent.profile.role_class
                attributes_of_class = role_class and quest.attributes_by_class.get(role_class.name, None)
                if attributes_of_class is None:
                    log.warning(u'Unsupported role class by class quest: {}'.format(role_class.name))
                else:
                    if agent.car:

                        # is_ancestor
                        log.info("Test car for agents!!")

                        quest.npc_replica(
                            npc=quest.hirer,
                            replica=quest.locale("q_GetClassCarQuestNote not good car!"),  ##LOCALIZATION
                            event=event
                        )
                    else:
                        quest.npc_replica(
                            npc=quest.hirer,
                            replica=quest.locale("q_GetClassCarQuestNote where u car?"),  ##LOCALIZATION
                            event=event
                        )







    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_cq_final"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
