# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnNote, OnTimer
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField, LocalizedString
from sublayers_server.model.units import Bot

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestShadowing(ClassTypeQuest):
    count = IntField(caption=u"Количество удачных слежек")
    shadowing_duration = IntField(caption=u"Количество удачных слежек")
    shadowing_check_interval = IntField(root_default=5, caption=u"Интервал проверки слежки, секунды")

    def init_text(self):
        self.text = LocalizedString(_id="q_cq_journal_text").generate(
            player_name=self.agent.login, task_text=self.locale("q_cq_shadowing_task_text"))  ##LOCALIZATION

    def on_start_(self, event, **kw):
        self.init_text()
        self.dc.uids = []  # Список uids, подвергшихся удачным слежкам
        self.dc.shadowings = dict()  # Счётчик uid машинок, за которыми сейчас ведётся слежка
        self.log(text=self.locale("q_cq_shadowing_started"), event=event)  ##LOCALIZATION


    def check_shadowing(self, event):
        agent_car = self.agent.profile._agent_model.car
        if agent_car is None:
            return
        # Пройти по всем отслеживаемым машинкам. проверяя, видят ли они нас
        shadowings_list = self.dc.shadowings.keys()
        for obj_uid in shadowings_list:
            obj = event.server.objects.get(obj_uid, None)
            if not obj or not obj.main_agent or not obj.is_alive:  # Если не нашли объект
                del self.dc.shadowings[obj_uid]  # Удаляем слежку
            else:
                if obj.main_agent.check_visible(agent_car):  # Если цель нас видит
                    self.dc.shadowings[obj_uid] = 0  # Сбрасываем, так как считаем, что нас заметили
                    text = LocalizedString(_id='q_cq_shadowing_break_target').generate(
                        target_login=obj.main_agent.print_login())  ##LOCALIZATION
                    self.log(text=text, event=event, game_log_only=True)
                elif obj not in agent_car.visible_objects:  # если мы потеряли цель
                    del self.dc.shadowings[obj_uid]  # Удаляем слежку
                    text = LocalizedString(_id='q_cq_shadowing_lost_target').generate(
                        target_login=obj.main_agent.print_login(), game_log_only=True)  ##LOCALIZATION
                    self.log(text=text, event=event)
                else:  # Слежка проходит успешно, прибавляем значение интервала
                    if self.dc.shadowings[obj_uid] == 0:
                        # print(u"Начнём следить! для {}".format(target.main_agent.uid))
                        text = LocalizedString(_id='q_cq_shadowing_start_target').generate(
                            target_login=obj.main_agent.print_login())  ##LOCALIZATION
                        self.log(text=text, event=event, game_log_only=True)
                    self.dc.shadowings[obj_uid] += self.shadowing_check_interval
                    # Проверить, а не завершена ли слежка
                    if self.dc.shadowings[obj_uid] > self.shadowing_duration: # Слежка завершена
                        self.dc.uids.append(obj.main_agent.uid)
                        del self.dc.shadowings[obj_uid]
                        text = LocalizedString(_id='q_cq_shadowing_one_template').generate(
                            target_login=obj.main_agent.print_login())  ##LOCALIZATION
                        self.log(text=text, event=event)

        # пройти по всем видимым машинкам, которых мы раньше не видели добавить и начать слежку за ними
        for target in agent_car.visible_objects:
            if isinstance(target, Bot) and target.main_agent.uid not in self.dc.uids and target.uid not in self.dc.shadowings:
                self.dc.shadowings[target.uid] = 0


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.quest_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.ShadowingQuestNote,
                time=event.time,
                page_caption=quest.locale("q_cq_shadowing_finished_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_shadowing_finished_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

            quest.set_timer(event=event, name='shadowing', delay=quest.shadowing_check_interval)

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                if quest.count <= len(quest.dc.uids):
                    quest.go(event=event, new_state="back_to_teacher")
                else:
                    text = LocalizedString(_id="q_cq_shadowing_replica_not_finish").generate(  ##LOCALIZATION
                        count=quest.count,
                        complete=len(quest.dc.uids)
                    )
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=text,
                        event=event
                    )

            if isinstance(event, OnTimer) and event.name == 'shadowing':
                quest.set_timer(event=event, name='shadowing', delay=quest.shadowing_check_interval)
                quest.check_shadowing(event=event)
                if quest.count <= len(quest.dc.uids):
                    quest.log(text=quest.locale("q_cq_shadowing_back_to_teacher"), event=event)  ##LOCALIZATION
                    quest.go(event=event, new_state="back_to_teacher")

    class back_to_teacher(QuestState_):
        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                quest.agent.profile.del_note(uid=quest.dc.quest_note, time=event.time)
                quest.go(event=event, new_state="win")

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.npc_replica(
                npc=quest.hirer,
                replica=quest.locale("q_cq_shadowing_phrase_success"),  ##LOCALIZATION
                event=event
            )
            quest.log(text=quest.locale("q_cq_shadowing_finished"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
