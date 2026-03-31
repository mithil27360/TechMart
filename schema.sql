create table users (
    user_id int auto_increment primary key,
    name varchar(100) not null,
    email varchar(100) unique not null,
    password varchar(100) not null,
    role varchar(10) not null,
    google_id varchar(255) unique,
    is_verified boolean default false,
    otp_token varchar(6),
    otp_expiry timestamp null,
    created_at timestamp default current_timestamp,
    constraint chk_role check (role in ('buyer', 'seller', 'admin'))
);

create table categories (
    category_id int auto_increment primary key,
    name varchar(100) not null,
    parent_id int,
    description text,
    foreign key (parent_id) references categories(category_id)
        on delete set null
);

create table items (
    item_id int auto_increment primary key,
    title varchar(150) not null,
    description text,
    price decimal(10,2) not null,
    category_id int,
    seller_id int,
    item_condition varchar(20) default 'new',
    quantity int default 1,
    created_at timestamp default current_timestamp,
    updated_at timestamp default current_timestamp on update current_timestamp,
    foreign key (category_id) references categories(category_id)
        on delete set null,
    foreign key (seller_id) references users(user_id)
        on delete cascade,
    constraint chk_price check (price > 0),
    constraint chk_quantity check (quantity >= 0),
    constraint chk_condition check (item_condition in ('new', 'used', 'refurbished'))
);

create table interests (
    interest_id int auto_increment primary key,
    user_id int,
    category_id int,
    keyword varchar(100),
    min_price decimal(10,2),
    max_price decimal(10,2),
    item_condition varchar(20),
    active boolean default true,
    created_at timestamp default current_timestamp,
    foreign key (user_id) references users(user_id)
        on delete cascade,
    foreign key (category_id) references categories(category_id)
        on delete cascade
);

create table notifications (
    notification_id int auto_increment primary key,
    user_id int,
    item_id int,
    interest_id int,
    is_read boolean default false,
    message text,
    sent_at timestamp default current_timestamp,
    foreign key (user_id) references users(user_id)
        on delete cascade,
    foreign key (item_id) references items(item_id)
        on delete cascade,
    foreign key (interest_id) references interests(interest_id)
        on delete set null
);

create table orders (
    order_id int auto_increment primary key,
    item_id int,
    buyer_id int,
    seller_id int,
    quantity int default 1,
    total_price decimal(10,2),
    order_date timestamp default current_timestamp,
    status varchar(20) default 'pending',
    notes text,
    foreign key (item_id) references items(item_id) on delete set null,
    foreign key (buyer_id) references users(user_id) on delete cascade,
    foreign key (seller_id) references users(user_id) on delete cascade
);

create table wishlist (
    wishlist_id int auto_increment primary key,
    user_id int,
    item_id int,
    created_at timestamp default current_timestamp,
    foreign key (user_id) references users(user_id) on delete cascade,
    foreign key (item_id) references items(item_id) on delete cascade,
    unique (user_id, item_id)
);

create table search_history (
    search_id int auto_increment primary key,
    user_id int,
    query varchar(255),
    category_id int,
    min_price decimal(10,2),
    max_price decimal(10,2),
    searched_at timestamp default current_timestamp,
    foreign key (user_id) references users(user_id) on delete cascade
);

-- Indexes
create index idx_items_cat on items(category_id);
create index idx_items_price on items(price);
create index idx_interests_user on interests(user_id);
create index idx_notif_user on notifications(user_id);
create index idx_matching_interests on interests(category_id, min_price, max_price);

-- Seeding Initial Data
insert into users (name, email, password, role) values
('Rahul', 'rahul@gmail.com', '123', 'buyer'),
('Ananya', 'ananya@gmail.com', '123', 'seller'),
('Kiran', 'kiran@gmail.com', '123', 'buyer'),
('Administrator', 'admin@techmart.com', 'admin123', 'admin');

insert into categories (name, parent_id) values
('Electronics', null), ('Phones', 1), ('Laptops', 1);

insert into items (title, description, price, category_id, seller_id, item_condition, quantity) values
('iPhone 13', 'Good condition, 1 year old', 50000, 2, 2, 'used', 5),
('MacBook Air', 'Silicon M1, Space Grey', 75000, 3, 2, 'new', 3),
('Mac Studio Silicon M2', 'Ultra performance desktop', 150000, 1, 2, 'new', 2);

-- PROCEDURES
delimiter $$
create procedure get_notifications(in p_user_id int)
begin
    select n.*, i.title, i.price 
    from notifications n
    join items i on n.item_id = i.item_id
    where n.user_id = p_user_id
    order by n.sent_at desc;
end $$

create procedure mark_notification_read(in p_notif_id int, in p_user_id int)
begin
    update notifications set is_read = true 
    where notification_id = p_notif_id and user_id = p_user_id;
end $$
delimiter ;

-- Trigger: Advanced Search matching
delimiter $$
create trigger notify_users_after_item
after insert on items
for each row
begin
    insert into notifications(user_id, item_id, interest_id, message)
    select i.user_id, new.item_id, i.interest_id, 
           concat('New ', new.title, ' available in ', (select name from categories where category_id=new.category_id))
    from interests i
    where i.active = true
    and (i.category_id is null or i.category_id = new.category_id)
    and (i.min_price is null or new.price >= i.min_price)
    and (i.max_price is null or new.price <= i.max_price)
    and (i.item_condition is null or i.item_condition = new.item_condition)
    and (i.keyword is null or new.title like concat('%', i.keyword, '%') or new.description like concat('%', i.keyword, '%'));
end $$

-- New Trigger: Seller Order alerts
create trigger notify_seller_after_order
after insert on orders
for each row
begin
    insert into notifications(user_id, item_id, message)
    values (new.seller_id, new.item_id, 
           concat('You have a new order for ', (select title from items where item_id=new.item_id), ' from ', (select name from users where user_id=new.buyer_id)));
end $$
delimiter ;
