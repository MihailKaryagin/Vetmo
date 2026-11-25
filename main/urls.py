from django.urls import path
from . import views
from . import support
from . import community
from . import journeys
from . import guild
from .services import limit_posts
from django.contrib.auth import views as auth_views

# name используется в reverse() и тегах шаблонов url; pk — идентификатор записи.
urlpatterns = [
    path('game-day/', guild.game_day, name='game_day'),
    path('party/<int:pk>/roster/<str:action>/', guild.roster_action, name='roster_action'),
    path('account/searches/save/', guild.save_search, name='save_search'),
    path('matches/<int:pk>/', journeys.match_detail, name='match_detail'),
    path('matches/<int:pk>/refresh/', journeys.match_refresh, name='match_refresh'),
    path('events/<int:pk>/calendar/', journeys.event_calendar, name='event_calendar'),
    path('party/<int:pk>/start/', journeys.party_start, name='party_start'),
    path('party/<int:pk>/confirm/', journeys.party_confirm, name='party_confirm'),
    path('party/<int:pk>/calendar/', journeys.party_calendar, name='party_calendar'),
    path('', views.index, name='root'),
    path('account/', views.account, name='account'),
    path('account/email/', community.account_email, name='account_email'),
    path('account/signup/', views.signup, name='signup'),
    path('account/login/', limit_posts(auth_views.LoginView.as_view()), name='login'),
    path('account/reset/', limit_posts(auth_views.PasswordResetView.as_view()), name='password_reset'),
    path('account/reset/sent/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('account/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('account/reset/complete/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('account/notifications/count/', community.notification_count, name='notification_count'),
    path('account/favorites/', community.favorites, name='favorites'),
    path('account/favorites/<int:pk>/remove/', community.favorite_remove, name='favorite_remove'),
    path('favorites/<str:kind>/<int:pk>/', community.favorite_toggle, name='favorite_toggle'),
    path('account/orders/<uuid:pk>/cancel/', community.order_cancel, name='order_cancel'),
    path('matches', community.matches, name='matches'),
    path('tournaments', community.tournaments, name='tournaments'),
    path('tournaments/<int:pk>/', community.tournament_detail, name='tournament_detail'),
    path('polls', community.polls, name='polls'),
    path('polls/<int:pk>/vote/', community.poll_vote, name='poll_vote'),
    path('events/<int:pk>/cancel', community.event_cancel, name='event_cancel'),
    path('party/<int:pk>/responses/<int:response_pk>/', community.party_accept, name='party_accept'),
    path('account/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('account/password/', auth_views.PasswordChangeView.as_view(success_url='/account/'), name='password_change'),
    path('account/notifications/read/', views.notifications_read, name='notifications_read'),
    path('account/orders/<uuid:pk>/', views.account_order, name='account_order'),
    path('support/messages', support.messages, name='support_messages'),
    path('main', views.index, name='start'),
    path('news', views.news_view, name='news'),
    path('how-we-play', views.prod_view, name='prod'),
    path('blog', views.blog_view, name='blog'),
    path('publications/<int:pk>/', views.publication_detail, name='publication_detail'),
    path('about', views.about_view, name='about'),
    path('communities/', views.communities_view, name='communities'),
    path('home', views.home_view, name='home'),
    # Отдельные маршруты отображают анкету и принимают результат её отправки.
    path('join', views.myform, name='myform'),
    path('join/result', views.obr_view, name='obr_result'),
    path('store', views.store, name='store'),
    path('store/<int:pk>/order', views.merch_order, name='merch_order'),
    path('store/<int:pk>/', views.product_detail, name='product_detail'),
    path('store/order/success', views.order_success, name='order_success'),
    path('join/saved', views.recruitment_success, name='recruitment_success'),
    path('players/<int:pk>/', views.player_detail, name='player_detail'),
    path('party/<int:pk>/', views.party_detail, name='party_detail'),
    path('party/<int:pk>/close', views.party_close, name='party_close'),
    path('party/<int:pk>/edit', views.party_edit, name='party_edit'),
    path('players', views.people_view, name='people'),
    path('events', views.events_view, name='events'),
    path('events/<int:pk>/register', views.event_register, name='event_register'),
    path('party', views.party_view, name='party'),

]
