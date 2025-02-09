# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState
from sublayers_server.model.quest_events import OnNote, OnMakeDmg
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField, RegistryLinkField, ListField, LocalizedString
from sublayers_server.model.messages import ArcadeTextMessage
from sublayers_world.registry.quests.class_quests import ClassTypeQuest


class ClassQuestDamageMapWeapon(ClassTypeQuest):
    count = IntField(caption=u"Количество удачных попаданий")

    available_activate_items = ListField(
        caption=u"Список разрешённых айтемов",
        field=RegistryLinkField(document_type='sublayers_server.model.registry_me.classes.mobiles.ExtraMobile'),
    )

    def init_text(self):
        sub_text = LocalizedString(_id="q_cq_dmg_map_weapon_task_text").generate(
            role_class_name=self.locale(self.agent.profile.role_class.title)
        )
        self.text = LocalizedString(
            en=u"{}<br>{}".format(
                sub_text.get(lang="en"),
                self.locale(key="q_cq_journal_reward_2", loc="en"),
            ),
            ru=u"{}<br>{}".format(
                sub_text.get(lang="ru"),
                self.locale(key="q_cq_journal_reward_2", loc="ru"),
            ),
        )

    def on_start_(self, event, **kw):
        self.init_text()
        self.dc.count_done = 0  # Количество удачных попаданий
        self.log(text=self.locale("q_cq_dmg_map_weapon_started"), event=event)  ##LOCALIZATION

    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.quest_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.DamageMapWeaponQuestNote,
                time=event.time,
                page_caption=quest.locale("q_cq_dmg_map_weapon_finished_page"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_cq_dmg_map_weapon_finished_btn"),  ##LOCALIZATION
                npc=quest.hirer,
            )

        def on_event_(self, quest, event):
            if isinstance(event, OnNote) and (event.note_uid == quest.dc.quest_note):
                if quest.count <= quest.dc.count_done:
                    quest.go(event=event, new_state="back_to_teacher")
                else:
                    text = LocalizedString(_id="q_cq_dmg_map_weapon_replica_not_finish").generate(  ##LOCALIZATION
                        compete=quest.dc.count_done,
                        count=quest.count
                    )
                    quest.npc_replica(
                        npc=quest.hirer,
                        replica=text,
                        event=event
                    )

            if isinstance(event, OnMakeDmg) and event.damager is not None:
                damager_ex = event.damager.example
                for candidate in quest.available_activate_items:
                    if damager_ex.is_ancestor(candidate):
                        quest.dc.count_done += 1
                        ArcadeTextMessage(agent=quest.agent.profile._agent_model, time=event.time,
                                          arcade_message_type='rocket_hit').post()
                        text = LocalizedString(_id='q_cq_dmg_map_weapon_add_one').generate(title=quest.locale(damager_ex.title))  ##LOCALIZATION
                        quest.log(text=text, event=event)
                        break
                if quest.count <= quest.dc.count_done:
                    quest.log(text=quest.locale("q_cq_dmg_map_weapon_back_to_teacher"), event=event)  ##LOCALIZATION
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
            quest.npc_replica(
                npc=quest.hirer,
                replica=quest.locale("q_cq_dmg_map_weapon_phrase_success"),  ##LOCALIZATION
                event=event
            )
            quest.log(text=quest.locale("q_cq_dmg_map_weapon_finished"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest
