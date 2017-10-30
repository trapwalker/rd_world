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
    RegistryLinkField,
)

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class StartQuest(ClassTypeQuest):
    class RoleClassQuestAttributes(Subdoc):
        teacher = LocalizedStringField(caption=u'Тип NPC-наставника (род. падеж)')
        artefact = LocalizedStringField(caption=u'Классовый артефакт')
        super_task = LocalizedStringField(caption=u'Классовая суперзадача')
        class_item = RegistryLinkField(
            document_type='sublayers_server.model.registry_me.classes.quest_item.QuestItem',
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
        # Создание ноты для квеста
        self.init_text()
        self.log(text=self.locale("q_cq_started"), event=event)  ##LOCALIZATION
        self.dc.teacher = None

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
                role_class = quest.agent.profile.role_class
                attributes_of_class = quest.attributes_by_class.get(role_class.name, None)
                if attributes_of_class is None:
                    log.warning(u'Unsupported role class by class quest: {}'.format(role_class.name))
                else:
                    quest.caption = attributes_of_class.super_task

                quest.init_text()
                quest.log(text=quest.locale("q_cq_caption_get_new_task"), event=event)  ##LOCALIZATION
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
                page_caption=quest.locale("q_cq_class_target_note"),  ##LOCALIZATION
                npc_type='trainer'
            )

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent.profile
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.visit_trainer_note_uid):
                quest.init_text()
                # todo: Вынести 300 в атрибуты квеста
                agent.set_exp(time=event.time, dvalue=300)
                quest.log(text=quest.locale("q_cq_visit_trainer"), event=event)  ##LOCALIZATION
                go("select_teacher")

    ####################################################################################################################
    class select_teacher(QuestState_):
        def on_enter_(self, quest, event):
            agent = quest.agent.profile
            quest.dc.select_teacher_note_uid = agent.add_note(
                quest_uid=quest.uid,
                note_class=notes.SelectTeacherNote,
                time=event.time,
                page_caption=quest.locale("q_cq_select_teacher_note_caption"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_select_teacher_note_btn")  ##LOCALIZATION
            )

        def on_event_(self, quest, event):
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
                            replica=quest.locale("q_cq_phrase_1"),  ##LOCALIZATION
                            event=event
                        )
                        return
                    if (agent.balance < 3000) or (agent.get_real_lvl() < 4):
                        quest.npc_replica(
                            npc=npc,
                            replica=quest.locale("q_cq_phrase_2"),  ##LOCALIZATION
                            event=event
                        )
                        return
                    else:
                        # todo: Вынести 3000 в атрибуты квеста
                        agent.set_balance(time=event.time, delta=-3000)
                        # todo: Вынести 500 в атрибуты квеста
                        agent.set_exp(time=event.time, dvalue=500)

                        # Выдаем классовый предмет
                        class_attrs = quest.attributes_by_class.get(agent.role_class.name, None)
                        if class_attrs:
                            class_item = class_attrs.class_item.instantiate()
                            agent.quest_inventory.add_item(agent=quest.agent, item=class_item, event=event)
                        else:
                            log.warninig('role class %r is not supported in ClassQuest', agent.role_class)
                            return

                        agent.del_note(uid=quest.dc.visit_trainer_note_uid, time=event.time)
                        agent.del_note(uid=quest.dc.select_teacher_note_uid, time=event.time)

                        quest.dc.teacher = npc  # Сохраняем выбранного учителя

                        go("win")
                else:
                    log.warning('ClassQuest get unknown NPC %s', event.npc_node_hash)

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_cq_final"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False)
            new_quest.hirer = quest.dc.teacher
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest