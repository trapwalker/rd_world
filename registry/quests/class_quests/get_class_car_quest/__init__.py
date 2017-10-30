# -*- coding: utf-8 -*-
import logging
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


class GetClassCarQuest(Quest):
    next_quest = RegistryLinkField(
        caption=u"Прототип классового квеста",
        document_type='sublayers_server.model.registry_me.classes.quests.Quest',
        root_default='reg:///registry/quests/class_quests/start_quest'
    )

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
         ##LOCALIZATION
        self.text = LocalizedString(
            en=u"Adventure will begin soon.",   ##LOCALIZATION
            ru=u"Приключение начнется скоро.",
        )
        if self.current_state == 'first_out':
            # todo: Вынести 300 в атрибуты квеста
            self.text = LocalizedString(
                en=u"Refer to trainer and learn more about purpose of their class.<br> Reward:<br>Exp 300",   ##LOCALIZATION
                ru=u"Обратиться к тренеру и узнать больше про свою классовую цель.<br> Награда:<br>Exp 300",
            )

        elif self.current_state == 'visit_trainer':
            role_class = self.agent.profile.role_class
            class_attrs = self.attributes_by_class.get(role_class.name, None)
            if class_attrs is None:
                log.warninig('role class %r is not supported in ClassQuest', role_class)
                return

            teacher = class_attrs.teacher
            reward = class_attrs.artefact

            # todo: Вынести 500 в атрибуты квеста
            self.text = LocalizedString(
                en=(   ##LOCALIZATION
                    u"To learn subtleties of role-playing class, you need to find a mentor. For class {} need such a mentor as {}.<br>"
                    u"Find a mentor on class specialization.<br>"
                    u"Reward: "
                    u"Exp: 500, class artifact {}."
                ).format(
                    role_class.description.en,
                    teacher.en,
                    reward.en,
                ),
                ru=(
                    u"Чтобы освоить тонкости ролевого класса нужно найти наставника. Для класса {} искать наставника стоит в лице {}.<br>"
                    u"Найти наставника по классовой специализации.<br>"
                    u"Награда: "
                    u"Exp: 500, классовый артефакт {}."
                ).format(
                    role_class.description.ru,
                    teacher.ru,
                    reward.ru,
                ),
            )

    def on_start_(self, event, **kw):
        self.init_text()
        self.log(text=self.locale("q_cq_started"), event=event)  ##LOCALIZATION


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.car_info_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.GetClassCarQuestNote,
                time=event.time,
                page_caption=quest.locale("q_GetClassCarQuestNote Page caption"),
                btn1_caption=quest.locale("q_GetClassCarQuestNote btn caption"),
                npc=quest.hirer,
            )

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
