# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.quest_events import OnCancel, OnTimer, OnNote, OnKill
from sublayers_server.model.registry_me.classes.quests import (
    Cancel, QuestState_, FailByCancelState, FailState, WinState,
)
from sublayers_server.model.registry_me.tree import (IntField, FloatField, ListField, EmbeddedDocumentField,
                                                     BooleanField, Subdoc, StringField, UUIDField)
from sublayers_server.model.registry_me.classes.quests import Quest, QuestRange
from sublayers_server.model.utils import getKarmaName

from functools import partial
import random


class KillerQuestVictim(Subdoc):
    login = StringField(doc=u"Имя жертвы", tags={'client'})
    photo = StringField(doc=u"Ссылка на аватарку жертвы", tags={'client'})

    def as_dict(self):
        return dict(
            login=self.login,
            photo=self.photo,
        )


class KillerQuest(Quest):
    unique_victims = BooleanField(caption=u'Должны ли быть жертвы уникальными')
    price_victim = IntField(caption=u'Цена одной жертвы на первом уровне квеста в нукойнах')
    count_to_kill_range = EmbeddedDocumentField(document_type=QuestRange, caption=u"Диапазон количетсва жертв")
    count_to_kill = IntField(caption=u'Количество убийств (вычислимый параметр)')
    max_karma_victims = IntField(caption=u'Максимальное значение кармы жертвы (вычислимый параметр)')
    min_level_victims = IntField(caption=u'Минимальный уровень жертвы')
    max_karma_victims_start = FloatField(caption=u'Максимальное значение кармы жертвы при 0 уровне квеста')
    max_karma_victims_by_lvl = FloatField(caption=u'Сколько кармы от стартовой будет отнимать каждый лвл квеста')
    deadline_koeff_by_lvl = FloatField(caption=u'На сколько больше времени будет выдаваться на каждую жертву в зависимости от уровня квеста')
    price_victim_koeff_by_lvl = FloatField(caption=u'На сколько больше будет суммарная награда в зависимости от уровня квеста')

    victims = ListField(
        root_default=list,
        field=EmbeddedDocumentField(
            document_type=KillerQuestVictim,
        ),
        caption=u"Список жертв (заполняется динамически)",
        reinst=True,  # todo: нужно узнать, нужно ли это здесь
    )

    def as_client_dict(self):
        d = super(KillerQuest, self).as_client_dict()
        d.update(
            victims=[victim.as_dict() for victim in self.victims],
            count_to_kill=self.count_to_kill,
        )
        return d

    def as_unstarted_quest_dict(self):
        d = super(KillerQuest, self).as_unstarted_quest_dict()
        d.update(count_to_kill=self.count_to_kill,)
        return d

    def get_available_lvl(self):
        # Уровень квеста зависит от отношений, но не выше уровня игрока
        relation = self.agent.profile.get_relationship(npc=self.hirer)
        # lvl_table = [-0.8, -0.6, 0.4, -0.2, 0, 0.2, 0.4, 0.6, 0.8, 1]
        lvl_table = [-0.8, 0, 1]
        max_relation_lvl = len(lvl_table)
        for item in lvl_table:
            if relation < item:
                max_relation_lvl = lvl_table.index(item)
        return min(self.agent.profile.get_lvl(), max_relation_lvl)

    def append_victim(self, agent, event):
        photo = "" if not agent.profile._agent_model else agent.profile._agent_model.avatar_link
        login = agent.login if not agent.profile._agent_model else agent.profile._agent_model.print_login()
        self.victims.append(KillerQuestVictim(login=login, photo=photo))

    def in_victims(self, agent):
        login = agent.login if not agent.profile._agent_model else agent.profile._agent_model.print_login()
        for victim in self.victims:
            if victim.login == login:
                return True
        return False

    def init_level(self):
        self.level = self.get_available_lvl()
        # Этот код нужен чтобы всегда генерить хотябы самый слабый квест
        if self.level == 0:
            self.level = 1
        self.level = random.randint(1, self.level)

    def init_targets_info(self):
        # чем выше уровень квеста, тем ниже максимальная карма жертвы
        self.max_karma_victims = self.max_karma_victims_start - self.level * self.max_karma_victims_by_lvl
        self.min_level_victims = self.level
        self.count_to_kill = self.count_to_kill_range.get_random_int()  # Выбираем сколько человек нужно убить

    def init_text(self):
        self.text_short = u"Убейте {:.0f} игрока(ов).".format(
            self.count_to_kill
        )
        self.text = u"Убейте {:.0f} игрока(ов) с минимальным уровнем {:.0f} и кармой хуже {}{}. Награда: {:.0f}nc, {:.0f} кармы и {:.0f} ед. опыта.".format(
            self.count_to_kill,
            self.min_level_victims,
            getKarmaName(self.max_karma_victims / 100., 'ru'),
            u"" if not self.deadline else u" за {}".format(self.deadline_to_str()),
            self.reward_money,
            self.reward_karma,
            self.reward_exp * self.count_to_kill,
        )

    def init_deadline(self):
        if self.deadline:
            all_time = self.count_to_kill * self.deadline * (1 + self.level / self.deadline_koeff_by_lvl)
            # Время выделенное на квест кратно 5 минутам
            self.deadline = (all_time / 300) * 300 + (300 if (all_time % 300) > 0 else 0)

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        if not self.can_generate(event):
            raise Cancel("QUEST CANCEL: reason: generate rules")

        # Установить уровень квеста, условия выполнения (определение жертв) и дедлайн
        self.init_level()
        self.init_targets_info()
        self.init_deadline()

        # Рассчитываем общую награду квеста - зависит от уровня квеста
        self.total_reward_money = self.count_to_kill * self.price_victim * (
        1 + self.level * self.price_victim_koeff_by_lvl)
        self.generate_reward()  # Устанавливаем награду за квест (карму, деньги и итемы)
        self.init_text()
    
    ####################################################################################################################
    def on_start_(self, event, **kw):
        if self.get_available_lvl() < self.level:
            self.npc_replica(npc=self.hirer, replica=u"NPC не достаточно хорошо к Вам относится.", event=event)
            raise Cancel("KillerQuest: User have not enough relation")
        # Создание ноты для квеста
        self.dc.wanted_note_uid = self.agent.profile.add_note(
            quest_uid=self.uid,
            note_class=notes.NPCWantedNote,
            time=event.time,
            npc=self.hirer,
            page_caption='Задание на убийство',
        )
        self.log(text=u'Начат квест на убийство. Целей {}.'.format(self.count_to_kill), event=event,
                 position=self.hirer.hometown.position)
    
    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            # Создание таймера deadline на убийство
            if quest.deadline:
                quest.set_timer(event=event, name='deadline_killer_quest', delay=quest.deadline)
    
        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
            if isinstance(event, OnKill):
                if ((event.agent.profile.karma <= quest.max_karma_victims) and
                        (event.agent.profile.get_real_lvl() >= quest.min_level_victims) and
                        (not quest.unique_victims or not quest.in_victims(event.agent))):
                    if event.agent and event.agent.profile and event.agent.profile._agent_model:
                        quest.append_victim(event.agent, event)  # todo: Исправить добавление агента
                        quest.log(text=u'{} убит.'.format(event.agent.profile._agent_model.print_login()), event=event,
                                  position=quest.hirer.hometown.position)  # todo: заменить на позицию машинки убийцы
                        quest.agent.profile.set_exp(time=event.time, dvalue=quest.reward_exp)
                        if len(quest.victims) >= quest.count_to_kill:
                            quest.log(text=u'Возвращайтесь за наградой.', event=event,
                                      position=quest.hirer.hometown.position)
                            go('note_kill_reward')

            if isinstance(event, OnTimer) and event.name == 'deadline_killer_quest':
                agent.profile.del_note(uid=quest.dc.wanted_note_uid, time=event.time)
                go("deadline_fail")

            if isinstance(event, OnCancel):
                penalty_money = quest.reward_money / 2.
                if agent.profile.balance >= penalty_money:
                    agent.profile.del_note(uid=quest.dc.wanted_note_uid, time=event.time)
                    agent.profile.set_balance(time=event.time, delta=-penalty_money)
                    quest.log(text=u'Уплачен штраф в размере {}nc.'.format(penalty_money), event=event,
                              position=quest.hirer.hometown.position)
                    go("cancel_fail")
                else:
                    quest.npc_replica(npc=quest.hirer,
                                      replica=u"Для отказа от квеста заплатите штраф {}nc.".format(penalty_money),
                                      event=event)

    ####################################################################################################################
    class note_kill_reward(QuestState_):
        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
            if isinstance(event, OnNote):
                if (quest.dc.wanted_note_uid == event.note_uid) and (event.result == True):
                    agent.profile.del_note(uid=quest.dc.wanted_note_uid, time=event.time)
                    go('reward')

    ####################################################################################################################
    class reward(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
            agent.profile.set_balance(time=event.time, delta=quest.reward_money)
            agent.profile.set_karma(time=event.time, dvalue=quest.reward_karma)
            quest.log(text=u'Получено вознаграждение в размере {:.0f}nc. и {:.0f} кармы'.format(quest.reward_money,
                                                                                                quest.reward_karma),
                      event=event, position=quest.hirer.hometown.position)
            agent.profile.set_relationship(time=event.time, npc=quest.hirer,
                                           dvalue=quest.reward_relation_hirer)  # изменение отношения к нпц
            if len(quest.reward_items) > 0:
                quest.dc.reward_note_uid = agent.profile.add_note(
                    quest_uid=quest.uid,
                    note_class=notes.NPCRewardItemsNote,
                    time=event.time,
                    npc=quest.hirer,
                    page_caption=u'Награда',
                    btn1_caption=u'<br>Забрать',
                )
            else:
                go('win')
    
        def on_event_(self, quest, event):
            if isinstance(event, OnNote):
                go = partial(quest.go, event=event)
                agent = quest.agent
                if (event.note_uid == quest.dc.reward_note_uid) and (event.result == True):
                    if quest.give_items(items=quest.reward_items, event=event):
                        agent.profile.del_note(uid=quest.dc.reward_note_uid, time=event.time)
                        go('win')
                    else:
                        quest.npc_replica(npc=quest.hirer, replica=u"Не хватает места в инвентаре.", event=event)

    ####################################################################################################################
    class cancel_fail(FailByCancelState):
        def on_enter_(self, quest, event):
            quest.log(text=u'Квест провален: отказ от выполнения.', event=event)

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
           quest.log(text=u'Квест выполнен.', event=event)

    ####################################################################################################################
    class deadline_fail(FailState):
        def on_enter_(self, quest, event):
            quest.agent.profile.set_relationship(time=event.time, npc=quest.hirer,
                                           dvalue=-quest.level * 2)  # изменение отношения c нпц
            quest.log(text=u'Квест провален: время вышло.', event=event)
    ####################################################################################################################