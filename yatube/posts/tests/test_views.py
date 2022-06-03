import shutil
import tempfile

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Comment, Follow, Group, Post

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


class PostPagesTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Post_writer')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.posts = {}
        for i in range(13):
            name = 'post{}'.format(i)
            cls.posts[name] = Post.objects.create(
                author=cls.user,
                text='Тестовый пост',
                group=cls.group,
            )
        cls.authorised_client = Client()
        cls.authorised_client.force_login(cls.user)
        cls.guest_client = Client()

    def test_pages_uses_correct_template(self):
        '''URL - адрес использует соответствующий шаблон'''
        id_post = PostPagesTest.posts['post0'].id
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            (
                reverse('posts:group_list', kwargs={'slug': 'test-slug'})
            ): 'posts/group_list.html',
            (
                reverse('posts:profile', kwargs={'username': 'Post_writer'})
            ): 'posts/profile.html',
            (
                reverse('posts:post_detail', kwargs={
                        'post_id': id_post})
            ): 'posts/post_detail.html',
            (
                reverse('posts:post_edit', kwargs={
                        'post_id': id_post})
            ): 'posts/create_post.html',
            reverse('posts:post_create'): 'posts/create_post.html',
        }
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorised_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_home_page_show_correct_context(self):
        '''Шаблон index сформирован с правильным контекстом(список постов)'''
        page = Post.objects.select_related('author', 'group').all()[:10]
        response = self.authorised_client.get(reverse('posts:index'))
        self.assertEqual(
            list(response.context.get('page_obj').object_list), list(page)
        )

    def test_page_show_correct_context_group(self):
        '''Шаблон group_list сформирован
        с правильным контекстом(список постов, отфильтрованных по группе)'''
        page = Post.objects.filter(group=self.group).all()[:10]
        response = self.authorised_client.get(
            reverse('posts:group_list', kwargs={'slug': 'test-slug'}))
        self.assertEqual(list(response.context.get(
            'page_obj').object_list), list(page))

    def test_page_show_correct_context_author(self):
        '''Шаблон profile сформирован
        с правильным контекстом
        (список постов, отфильтрованных по пользователю)'''
        page = Post.objects.filter(author=self.user).all()[:10]
        response = self.authorised_client.get(
            reverse('posts:profile', kwargs={'username': 'Post_writer'}))
        self.assertEqual(list(response.context.get(
            'page_obj').object_list), list(page))

    def test_post_page_show_correct_context_post_detail(self):
        '''Шаблон post_detail сформирован
        с правильным контекстом
        (один пост, отфильтрованный по id)'''
        self.user2 = User.objects.create_user(username='Post_writer2')
        self.post14 = Post.objects.create(
            author=self.user2,
            text='Тестовый пост от Post_writer2',
        )
        response = self.authorised_client.get(
            reverse('posts:post_detail', kwargs={'post_id': 14}))
        page_post = response.context['post'].text
        self.assertEqual(page_post, self.post14.text)

    def test_post_page_show_correct_context_post_edit(self):
        '''Шаблон post_detail сформирован
        с правильным контекстом
        (форма редактирования поста, отфильтрованного по id)'''
        response = self.authorised_client.get(
            reverse('posts:post_edit', kwargs={'post_id': 10}))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_page_show_correct_context_creaete_post(self):
        '''Шаблон post_create сформирован
        с правильным контекстом
        (форма создания поста)'''
        response = self.authorised_client.get(
            reverse('posts:post_create')
        )
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)
        group_test = Group.objects.create(
            title='Тестовая группа 2',
            slug='test-slug2',
            description='Тестовое описание',
        )
        post_test = Post.objects.create(
            author=self.user,
            text='Тестовый пост',
            group=group_test,
        )
        addresses = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': 'test-slug2'}),
            reverse('posts:profile', kwargs={'username': 'Post_writer'}),
        ]
        # проверяем, что пост появляется на:
        # главной странице
        # странице группы
        # профайле пользователя
        for address in addresses:
            response = self.authorised_client.get(address)
            last_object_id = response.context['page_obj'][0].id
            self.assertEqual(last_object_id, post_test.id)
        # проверяем, что пост не попал в другую группу
        response = self.authorised_client.get(
            reverse('posts:group_list', kwargs={'slug': 'test-slug'}))
        last_object_id = response.context['page_obj'][0].id
        self.assertNotEqual(last_object_id, post_test.id)


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Post_writer')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.posts = {}
        for i in range(13):
            name = 'post{}'.format(i)
            cls.posts[name] = Post.objects.create(
                author=cls.user,
                text='Тестовый пост',
                group=cls.group
            )
        cls.authorised_client = Client()
        cls.authorised_client.force_login(cls.user)
        cls.guest_client = Client()

    def test_first_page_contains_ten_records(self):
        '''На первой странице отображается 10 постов'''
        addresses = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': 'test-slug'}),
            reverse('posts:profile', kwargs={'username': 'Post_writer'}),
        ]
        for address in addresses:
            response = self.authorised_client.get(address)
            self.assertEqual(len(response.context['page_obj']), 10)

    def test_second_page_contains_three_records(self):
        '''На второй странице отображается 3 поста'''
        addresses = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': 'test-slug'}),
            reverse('posts:profile', kwargs={'username': 'Post_writer'}),
        ]
        for address in addresses:
            response = self.authorised_client.get(address + '?page=2')
            self.assertEqual(len(response.context['page_obj']), 3)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostImageTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Post_writer')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.authorised_client = Client()
        cls.authorised_client.force_login(cls.user)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def test_create_post_with_image(self):
        """Изображение передается в словаре context на страницы"""
        tasks_count_before = Post.objects.count()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )

        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.id,
            'image': uploaded,
        }
        self.authorised_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True,
        )
        tasks_count_after = Post.objects.count()
        # создается запись в БД
        self.assertEqual(tasks_count_before + 1, tasks_count_after)
        # Изображение передается на:
        # главную страницу
        # страницу группы
        # страницу профайла
        addresses = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': 'test-slug'}),
            reverse('posts:profile', kwargs={'username': 'Post_writer'}),
        ]
        for address in addresses:
            response = self.authorised_client.get(address)
            post = response.context['page_obj'][0]
            image = post.image
            self.assertEqual(image, 'posts/small.gif')
        # страницу поста
        response = self.authorised_client.get(
            reverse('posts:post_detail', kwargs={'post_id': 1})
        )
        post = response.context['post']
        image = post.image
        self.assertEqual(image, 'posts/small.gif')


class PostCommentTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Post_writer')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
        )
        cls.authorised_client = Client()
        cls.authorised_client.force_login(cls.user)

    def test_comment_appear_post_page(self):
        '''Комментарий появляется на странице поста'''
        id_post = PostCommentTest.post.id
        self.authorised_client.post(
            reverse('posts:add_comment', kwargs={'post_id': id_post}),
            data={'text': 'New comment'},
        )
        response = self.authorised_client.get(
            reverse('posts:post_detail', kwargs={'post_id': id_post})
        )
        comment_page = list(response.context.get('comments'))[0]
        comment_bd = Comment.objects.get(pk=id_post)
        self.assertEqual(comment_page, comment_bd)


class CasheTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Post_writer')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
        )
        cls.guest_client = Client()

    def test_index_page_cashe(self):
        '''Тестирование работы кэша на странице index'''
        id_post = CasheTest.post.id
        response_before_del = self.guest_client.get(reverse('posts:index'))
        Post.objects.filter(pk=id_post).delete()
        response_after_del = self.guest_client.get(reverse('posts:index'))
        self.assertEqual(
            response_before_del.content, response_after_del.content
        )


class FollowTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user1 = User.objects.create_user(username='Post_writer')
        cls.user2 = User.objects.create_user(username='User')
        cls.user3 = User.objects.create_user(username='Non_post_writer')
        cls.post = Post.objects.create(
            author=cls.user1,
            text='Тестовый пост',
        )
        cls.authorised_client1 = Client()
        cls.authorised_client2 = Client()
        cls.authorised_client1.force_login(cls.user2)
        cls.authorised_client2.force_login(cls.user3)
        cls.guest_client = Client()

    def test_authorized_user_follow_author(self):
        '''Пользователь User подписывается на пользователя Post_writer'''
        following = False
        self.authorised_client1.get(
            reverse('posts:profile_follow', kwargs={'username': 'Post_writer'})
        )
        if Follow.objects.filter(user=FollowTest.user2).exists():
            authors_follow = Follow.objects.values(
                'author_id').filter(user=FollowTest.user2).all()
            list_id = [id['author_id'] for id in authors_follow]
            if FollowTest.user1.id in list_id:
                following = True
        self.assertTrue(following)

    def test_authorized_user_unfollow_author(self):
        '''Пользователь user отписывается от пользователя Post_writer'''
        self.authorised_client1.get(
            reverse('posts:profile_follow', kwargs={'username': 'Post_writer'})
        )
        if Follow.objects.filter(user=FollowTest.user2).exists():
            authors_follow = Follow.objects.values(
                'author_id').filter(user=FollowTest.user2).all()
            list_id = [id['author_id'] for id in authors_follow]
            if FollowTest.user1.id in list_id:
                following = True
        self.authorised_client1.get(
            reverse('posts:profile_unfollow',
                    kwargs={'username': 'Post_writer'}
                    )
        )
        if Follow.objects.filter(user=FollowTest.user2).exists():
            authors_follow = Follow.objects.values(
                'author_id').filter(user=FollowTest.user2).all()
            list_id = [id['author_id'] for id in authors_follow]
            if FollowTest.user1.id not in list_id:
                following = False
        else:
            following = False
        self.assertFalse(following)

    def test_nonauthorized_user_follow_author(self):
        '''Неавторизованный пользователь не может подписаться на автора'''
        count_follow_before = Follow.objects.count()
        response = self.guest_client.get(
            reverse('posts:profile_unfollow',
                    kwargs={'username': 'Post_writer'}
                    )
        )
        count_follow_after = Follow.objects.count()
        self.assertEqual(count_follow_before, count_follow_after)
        self.assertRedirects(
            response, (f'/auth/login/?next=/profile/'
                       f'{FollowTest.user1.username}/unfollow/'
                       )
        )

    def test_self_follow(self):
        '''Подписка на себя не создает запись в базе данных'''
        self.author_client = Client()
        self.author_client.force_login(FollowTest.user1)
        count_follow_before = Follow.objects.count()
        self.author_client.get(
            reverse('posts:profile_follow', kwargs={'username': 'Post_writer'})
        )
        count_follow_after = Follow.objects.count()
        self.assertEqual(count_follow_before, count_follow_after)

    def test_post_exist_page_follow_following_user(self):
        '''Пост автора Post_writer появляется на
        странице index_follow подписавшегося пользователя User'''
        self.authorised_client1.get(
            reverse('posts:profile_follow', kwargs={'username': 'Post_writer'})
        )
        response = self.authorised_client1.get(reverse('posts:follow_index'))
        last_object_id = response.context['page_obj'][0].id
        self.assertEqual(last_object_id, FollowTest.post.id)

    def test_post_not_exist_page_follow_nonfollowing_user(self):
        '''Пост автора Post_writer не появляется на
        странице index_follow не подписавшегося пользователя Non_post_writer'''
        self.post2 = Post.objects.create(
            author=self.user2,
            text='Тестовый пост user2',
        )
        self.authorised_client2.get(
            reverse('posts:profile_follow', kwargs={'username': 'User'})
        )
        response2 = self.authorised_client2.get(reverse('posts:follow_index'))
        last_object_id2 = response2.context['page_obj'][0].id
        self.assertNotEqual(last_object_id2, FollowTest.post.id)
