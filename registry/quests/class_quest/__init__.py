# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import Quest, QuestState_, WinState
from sublayers_server.model.quest_events import OnExitFromLocation, OnNote
from sublayers_server.model.registry_me.classes import notes
from functools import partial


class ClassQuest(Quest):

    def init_text(self):
        self.text = u"Приключение начнется скоро."
        if self.current_state == 'first_out':
            self.text = u"Обратиться к тренеру и узнать больше про свою классовую цель.<br> Награда:<br>Exp 300"
        elif self.current_state == 'visit_trainer':
            role_class = self.agent.profile.role_class
            teacher = ''
            reward = ''
            if (role_class.title == "Chosen One"):
                teacher = u'мэра'
                reward = u'Фляжка'
            elif (role_class.title == "Alpha Wolf"):
                teacher = u'мэра'
                reward = u'Почтовая сумка'
            elif (role_class.title == "Night Rider"):
                teacher = u'бармен'
                reward = u'Зубочистка'
            elif (role_class.title == "Oil Magnate"):
                teacher = u'торговца'
                reward = u'Трость'
            elif (role_class.title == "Road Warrior"):
                teacher = u'автодилера'
                reward = u'Куртка с одним рукавом'
            elif (role_class.title == "Techno Kinetic"):
                teacher = u'механика'
                reward = u'Плутоний'
            self.text = u"Чтобы освоить тонкости ролевого класса нужно найти наставника. Для класса {} искать наставника стоит в лице {}.<br>" \
                        u"Найти наставника по классовой специализации.<br>" \
                        u"Награда: " \
                        u"Exp: 500, классовый артефакт {}.".format(
                role_class.description__ru,
                teacher,
                reward
            )

    def on_start_(self, event, **kw):
        # Создание ноты для квеста
        self.init_text()
        self.log(text=u'Начат Классовый квест.'.format(), event=event)

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
                quest.init_text()
                quest.log(text=u'Получено новое задание.', event=event)
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
                page_caption=u'Классовая цель',
                npc_type='trainer'
            )

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent.profile
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.visit_trainer_note_uid):
                quest.init_text()
                agent.set_exp(time=event.time, dvalue=300)
                quest.log(text=u'Посещен тренер.', event=event)
                go("select_teacher")

    ####################################################################################################################
    class select_teacher(QuestState_):
        def on_enter_(self, quest, event):
            agent = quest.agent.profile
            quest.dc.select_teacher_note_uid = agent.add_note(
                quest_uid=quest.uid,
                note_class=notes.SelectTeacherNote,
                time=event.time,
                page_caption=u'Наставник',
                btn1_caption=u'<br>Принять'
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
                            replica=u"Мы недостаточно хорошо знакомы. Пока уровень отношений не будет на отметке как "
                                    u"минимум в 75, дальнейшего разговора не будет.</br> Отношение можно повысить "
                                    u"близостью в карме и выполнением моих заданий.",
                            event=event
                        )
                        return
                    if (agent.balance < 3000) or (agent.get_real_lvl() < 4):
                        quest.npc_replica(
                            npc=npc,
                            replica=u"Хорошо, вот мои требования к ученикам:</br>- Взнос 3000 NC.</br>- Уровень не менее 4.",
                            event=event
                        )
                        return
                    else:
                        agent.set_balance(time=event.time, delta=-3000)
                        agent.set_exp(time=event.time, dvalue=500)
                        agent.del_note(uid=quest.dc.visit_trainer_note_uid, time=event.time)
                        agent.del_note(uid=quest.dc.select_teacher_note_uid, time=event.time)
                        go("win")
                else:
                    log.warning('ClassQuest get unknown NPC %s', event.npc_node_hash)

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=u'Квест выполнен.', event=event)