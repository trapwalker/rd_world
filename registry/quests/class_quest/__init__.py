# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import Quest, QuestState_, WinState
from sublayers_server.model.quest_events import OnExitFromLocation, OnNote
from sublayers_server.model.registry_me.classes import notes
from functools import partial
from sublayers_server.model.registry_me.tree import (
    Subdoc, LocalizedString,
    MapField,
    LocalizedStringField,
    EmbeddedDocumentField,
    StringField,
)


class ClassQuest(Quest):
    class RoleClassQuestAttributes(Subdoc):
        teacher = LocalizedStringField(caption=u'Тип NPC-наставника (род. падеж)')
        artefact = LocalizedStringField(caption=u'Классовый артефакт')
        super_task = LocalizedStringField(caption=u'Классовая суперзадача')

    attributes_by_class = MapField(
        caption=u'Словарь атрибутов',
        field=EmbeddedDocumentField(document_type=RoleClassQuestAttributes),
    )

    def init_text(self):
        # TODO: ##LOCALIZATION
        self.text = LocalizedString(
            en=u"Приключение начнется скоро.",  # TODO: ##LOCALIZATION
            ru=u"Приключение начнется скоро.",
        )
        if self.current_state == 'first_out':
            # todo: Вынести 300 в атрибуты квеста
            self.text = LocalizedString(
                en=u"Обратиться к тренеру и узнать больше про свою классовую цель.<br> Награда:<br>Exp 300",  # TODO: ##LOCALIZATION
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
                en=(  # TODO: ##LOCALIZATION
                    u"Чтобы освоить тонкости ролевого класса нужно найти наставника. Для класса {} искать наставника стоит в лице {}.<br>"
                    u"Найти наставника по классовой специализации.<br>"
                    u"Награда: "
                    u"Exp: 500, классовый артефакт {}."
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
        # Создание ноты для квеста
        self.init_text()
        self.log(
            text=LocalizedString(
                en=u'Начат Классовый квест.',  # TODO: ##LOCALIZATION
                ru=u'Начат Классовый квест.',
            ),
            event=event,
        )

    ####################################################################################################################
    class first_out(QuestState_):
        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            if isinstance(event, OnExitFromLocation):
                quest.dc.first_out_note_uid = quest.agent.profile.add_note(
                    quest_uid=quest.uid,
                    note_class=notes.FirstOutNote,
                    time=event.time
                )
                # TODO: ##LOCALIZATION
                role_class = quest.agent.profile.role_class
                attributes_of_class = quest.attributes_by_class.get(role_class.name, None)
                if attributes_of_class is None:
                    log.warning(u'Unsupported role class by class quest: {}'.format(role_class.name))
                else:
                    quest.caption = attributes_of_class.super_task

                quest.init_text()
                quest.log(
                    text=LocalizedString(
                        en=u'Получено новое задание.',  # TODO: ##LOCALIZATION
                        ru=u'Получено новое задание.',
                    ),
                    event=event,
                )
                go("visit_trainer")

    ####################################################################################################################
    class visit_trainer(QuestState_):
        def on_enter_(self, quest, event):
            agent = quest.agent.profile
            agent.del_note(uid=quest.dc.first_out_note_uid, time=event.time)
            quest.dc.visit_trainer_note_uid = agent.add_note(
                quest_uid=quest.uid,
                note_class=notes.VisitTrainerNote,
                time=event.time,
                page_caption=LocalizedString(
                    en=u'Классовая цель',  # TODO: ##LOCALIZATION
                    ru=u'Классовая цель',
                ),
                npc_type='trainer'
            )

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent.profile
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.visit_trainer_note_uid):
                quest.init_text()
                # todo: Вынести 300 в атрибуты квеста
                agent.set_exp(time=event.time, dvalue=300)
                quest.log(
                    text=LocalizedString(
                        en=u'Посещен тренер.',  # TODO: ##LOCALIZATION
                        ru=u'Посещен тренер.',
                    ),
                    event=event,
                )  # TODO: ##LOCALIZATION
                go("select_teacher")

    ####################################################################################################################
    class select_teacher(QuestState_):
        def on_enter_(self, quest, event):
            # TODO: ##LOCALIZATION
            agent = quest.agent.profile
            quest.dc.select_teacher_note_uid = agent.add_note(
                quest_uid=quest.uid,
                note_class=notes.SelectTeacherNote,
                time=event.time,
                page_caption=LocalizedString(
                    en=u'Наставник',  # TODO: ##LOCALIZATION
                    ru=u'Наставник',  # TODO: ##LOCALIZATION
                ),
                btn1_caption=LocalizedString(
                    en=u'<br>Принять',  # TODO: ##LOCALIZATION
                    ru=u'<br>Принять',
                ),
            )

        def on_event_(self, quest, event):
            # TODO: ##LOCALIZATION
            go = partial(quest.go, event=event)
            agent = quest.agent.profile
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.select_teacher_note_uid):
                if not event.npc_node_hash:
                    log.warning('ClassQuest get empty NPC')
                    return
                npc = event.server.reg.get(event.npc_node_hash, None)
                if npc:
                    relation = agent.get_relationship(npc=npc)
                    if relation < 0.5:
                        quest.npc_replica(
                            npc=npc,
                            replica=LocalizedString(
                                en=(  # TODO: ##LOCALIZATION
                                    u"Мы недостаточно хорошо знакомы. Пока уровень отношений не будет на отметке как "
                                    u"минимум в 75, дальнейшего разговора не будет.</br> Отношение можно повысить "
                                    u"близостью в карме и выполнением моих заданий."
                                ),
                                ru=(
                                    u"Мы недостаточно хорошо знакомы. Пока уровень отношений не будет на отметке как "
                                    u"минимум в 75, дальнейшего разговора не будет.</br> Отношение можно повысить "
                                    u"близостью в карме и выполнением моих заданий."
                                ),
                            ),
                            event=event,
                        )
                        return
                    if (agent.balance < 3000) or (agent.get_real_lvl() < 4):
                        quest.npc_replica(
                            npc=npc,
                            # todo: Вынести 3000 в атрибуты квеста
                            replica=LocalizedString(
                                en=u"Хорошо, вот мои требования к ученикам:</br>- Взнос 3000 NC.</br>- Уровень не менее 4.",  # TODO: ##LOCALIZATION
                                ru=u"Хорошо, вот мои требования к ученикам:</br>- Взнос 3000 NC.</br>- Уровень не менее 4.",
                            ),
                            event=event,
                        )
                        return
                    else:
                        # todo: Вынести 3000 в атрибуты квеста
                        agent.set_balance(time=event.time, delta=-3000)
                        # todo: Вынести 500 в атрибуты квеста
                        agent.set_exp(time=event.time, dvalue=500)
                        agent.del_note(uid=quest.dc.visit_trainer_note_uid, time=event.time)
                        agent.del_note(uid=quest.dc.select_teacher_note_uid, time=event.time)
                        go("win")
                else:
                    log.warning('ClassQuest get unknown NPC %s', event.npc_node_hash)

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            # TODO: ##LOCALIZATION
            quest.log(
                text=LocalizedString(
                    en=u'Quest is complete.',  ##LOCALIZATION
                    ru=u'Квест выполнен.',
                ),
                event=event,
            )
