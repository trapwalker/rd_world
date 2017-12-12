# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnNote, OnMakeDmg
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField, LocalizedString
from sublayers_server.model.units import Bot

from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestInvisibleAttack(ClassTypeQuest):
    attack_count = IntField(caption=u"Количество атак из невидимости")

    def init_text(self):
        self.text = LocalizedString(
            en=u"{}<br>{}".format(
                self.locale(key="q_cq_inv_attack_task_text", loc="en"),
                self.locale(key="q_cq_journal_reward_2", loc="en"),
            ),
            ru=u"{}<br>{}".format(
                self.locale(key="q_cq_inv_attack_task_text", loc="ru"),
                self.locale(key="q_cq_journal_reward_2", loc="ru"),
            ),
        )

    def on_start_(self, event, **kw):
        self.init_text()
        self.dc.uids = []  # Список uid целей, подвергшихся атакам
        self.log(text=self.locale("q_cq_inv_attack_started"), event=event)  ##LOCALIZATION


    def invisible_attack_check(self, targets, event):
        agent_car = self.agent.profile._agent_model.car
        if agent_car is None:
            return
        for target in targets:
            if isinstance(target, Bot) and target.main_agent and not target.main_agent.check_visible(agent_car) and self.attack_count > len(self.dc.uids):
                if target.uid not in self.dc.uids:
                    self.dc.uids.append(target.uid)
                    left = self.attack_count - len(self.dc.uids)
                    text = LocalizedString(_id='q_cq_inv_attack_one_template').generate(
                        target_login=target.main_agent.print_login(),
                        left=left)  ##LOCALIZATION
                    self.log(text=text, event=event)
                    if left <= 0:
                        self.log(text=self.locale("q_cq_inv_attack_done"), event=event)


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.quest_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.InvisibleAttackQuestNote,
                time=event.time,
                page_caption=quest.locale("q_cq_inv_attack_finished_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_inv_attack_finished_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                if quest.attack_count <= len(quest.dc.uids):
                    quest.go(event=event, new_state="back_to_teacher")
                else:
                    text = LocalizedString(_id="q_cq_inv_attack_replica_not_finish").generate(  ##LOCALIZATION
                        attack_count=quest.attack_count,
                        attack_done=len(quest.dc.uids)
                    )
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=text,
                        event=event
                    )

            if isinstance(event, OnMakeDmg):
                quest.invisible_attack_check(targets=event.targets, event=event)
                if quest.attack_count <= len(quest.dc.uids):
                    quest.go(event=event, new_state="back_to_teacher")

    class back_to_teacher(QuestState_):
        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                quest.agent.profile.del_note(uid=quest.dc.quest_note, time=event.time)
                quest.agent.profile.set_exp(time=event.time, dvalue=5000)
                quest.go(event=event, new_state="win")

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            agent_example = quest.agent
            agent_profile = agent_example.profile

            replica = LocalizedString(_id='q_cq_inv_attack_phrase_success').generate(
                role_class_name=quest.locale(agent_profile.role_class.title)
            )
            quest.npc_replica(
                npc=quest.hirer,
                replica=replica,  ##LOCALIZATION
                event=event
            )
            quest.log(text=quest.locale("q_cq_inv_attack_finished"), event=event)  ##LOCALIZATION

            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
